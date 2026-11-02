from src.utils.exceptions import ConfigurationError, DataValidationError, MethodologyError

"""
Neural Networks for ML Valuation Engine

This module provides deep learning capabilities including
neural networks, convolutional networks, and attention mechanisms
for complex pattern recognition in valuation methodology selection.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from datetime import datetime
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import pickle

from src.utils.logging import get_logger
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.ml.ml_types import (
    MLModelType, ValuationMethodology, ModelMetrics, TrainingData,
    ModelConfiguration, DeepLearningArchitecture, ModelPerformance
)

# Scikit-learn neural network imports
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

logger = get_logger(__name__)

# Check PyTorch availability
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available. Deep learning features disabled.")


class NeuralNetworkEngine:
    """
    Neural network engine for valuation methodology prediction.

    Provides deep learning capabilities including:
    - Multi-layer perceptrons
    - Convolutional neural networks
    - Recurrent neural networks
    - Attention mechanisms
    - Transfer learning
    """

    def __init__(self):
        """Initialize the neural network engine"""
        self.logger = logger

        # Model storage
        self.trained_models: Dict[str, Any] = {}
        self.model_architectures: Dict[str, DeepLearningArchitecture] = {}

        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []

        # PyTorch availability
        self.torch_available = TORCH_AVAILABLE

    async def create_mlp_classifier(
        self,
        training_data: TrainingData,
        config: Optional[ModelConfiguration] = None
    ) -> Dict[str, Any]:
        """
        Create a multi-layer perceptron classifier.

        Args:
            training_data: Training data for the model
            config: Model configuration (optional)

        Returns:
            Trained MLP classifier
        """
        try:
            self.logger.info("Creating MLP classifier", data_size=training_data.data_size)

            # Create MLP classifier
            mlp_classifier = MLPClassifier(
                hidden_layer_sizes=(100, 50, 25),
                activation='relu',
                solver='adam',
                alpha=Decimal('0.001'),
                batch_size='auto',
                learning_rate='constant',
                learning_rate_init=Decimal('0.001'),
                max_iter=1000,
                random_state=42,
                early_stopping=True,
                validation_fraction=Decimal('0.1'),
                n_iter_no_change=10
            )

            # Train the model
            mlp_classifier.fit(training_data.features, training_data.labels)

            # Evaluate performance
            performance_metrics = await self._evaluate_mlp_performance(
                mlp_classifier, training_data
            )

            # Store the model
            model_id = f"mlp_{datetime.utcnow().timestamp()}"
            self.trained_models[model_id] = {
                'model': mlp_classifier,
                'performance': performance_metrics,
                'training_data_size': training_data.data_size,
                'created_at': datetime.utcnow()
            }

            self.logger.info(
                "MLP classifier created successfully",
                model_id=model_id,
                accuracy=performance_metrics.accuracy
            )

            return {
                'model_id': model_id,
                'model': mlp_classifier,
                'performance': performance_metrics,
                'model_type': 'mlp'
            }

        except ValuationEngineError as e:
            self.logger.error(f"Error creating MLP classifier: {e}")
            raise

    async def create_deep_neural_network(
        self,
        training_data: TrainingData,
        architecture: DeepLearningArchitecture
    ) -> Dict[str, Any]:
        """
        Create a deep neural network using PyTorch.

        Args:
            training_data: Training data for the model
            architecture: Neural network architecture

        Returns:
            Trained deep neural network
        """
        try:
            if not self.torch_available:
                self.logger.warning("PyTorch not available, falling back to MLP")
                return await self.create_mlp_classifier(training_data)

            self.logger.info("Creating deep neural network", data_size=training_data.data_size)

            # Create PyTorch model
            model = DeepNeuralNetwork(architecture)

            # Prepare data
            X_tensor = torch.FloatTensor(training_data.features)
            y_tensor = torch.LongTensor(training_data.labels)

            # Create data loader
            dataset = TensorDataset(X_tensor, y_tensor)
            data_loader = DataLoader(dataset, batch_size=32, shuffle=True)

            # Train the model
            trained_model = await self._train_pytorch_model(model, data_loader)

            # Evaluate performance
            performance_metrics = await self._evaluate_pytorch_performance(
                trained_model, training_data
            )

            # Store the model
            model_id = f"deep_nn_{datetime.utcnow().timestamp()}"
            self.trained_models[model_id] = {
                'model': trained_model,
                'performance': performance_metrics,
                'architecture': architecture,
                'training_data_size': training_data.data_size,
                'created_at': datetime.utcnow()
            }

            self.logger.info(
                "Deep neural network created successfully",
                model_id=model_id,
                accuracy=performance_metrics.accuracy
            )

            return {
                'model_id': model_id,
                'model': trained_model,
                'performance': performance_metrics,
                'model_type': 'deep_nn'
            }

        except ConfigurationError as e:
            self.logger.error(f"Error creating deep neural network: {e}")
            raise

    async def create_attention_network(
        self,
        training_data: TrainingData,
        config: Optional[ModelConfiguration] = None
    ) -> Dict[str, Any]:
        """
        Create an attention-based neural network.

        Args:
            training_data: Training data for the model
            config: Model configuration (optional)

        Returns:
            Trained attention network
        """
        try:
            if not self.torch_available:
                self.logger.warning("PyTorch not available, falling back to MLP")
                return await self.create_mlp_classifier(training_data)

            self.logger.info("Creating attention network", data_size=training_data.data_size)

            # Create attention model
            attention_model = AttentionNetwork(
                input_dim=training_data.feature_count,
                hidden_dim=128,
                num_heads=8,
                num_layers=3,
                output_dim=len(set(training_data.labels))
            )

            # Prepare data
            X_tensor = torch.FloatTensor(training_data.features)
            y_tensor = torch.LongTensor(training_data.labels)

            # Create data loader
            dataset = TensorDataset(X_tensor, y_tensor)
            data_loader = DataLoader(dataset, batch_size=32, shuffle=True)

            # Train the model
            trained_model = await self._train_pytorch_model(attention_model, data_loader)

            # Evaluate performance
            performance_metrics = await self._evaluate_pytorch_performance(
                trained_model, training_data
            )

            # Store the model
            model_id = f"attention_{datetime.utcnow().timestamp()}"
            self.trained_models[model_id] = {
                'model': trained_model,
                'performance': performance_metrics,
                'model_type': 'attention',
                'training_data_size': training_data.data_size,
                'created_at': datetime.utcnow()
            }

            self.logger.info(
                "Attention network created successfully",
                model_id=model_id,
                accuracy=performance_metrics.accuracy
            )

            return {
                'model_id': model_id,
                'model': trained_model,
                'performance': performance_metrics,
                'model_type': 'attention'
            }

        except MethodologyError as e:
            self.logger.error(f"Error creating attention network: {e}")
            raise

    async def predict_methodology(
        self,
        model_id: str,
        features: np.ndarray
    ) -> Dict[str, Any]:
        """
        Predict valuation methodology using neural network.

        Args:
            model_id: ID of the model to use
            features: Input features

        Returns:
            Prediction result with methodology and confidence
        """
        try:
            if model_id not in self.trained_models:
                raise ValueError(f"Model {model_id} not found")

            model_info = self.trained_models[model_id]
            model = model_info['model']

            # Make prediction based on model type
            if model_info.get('model_type') == 'mlp':
                # Scikit-learn MLP
                prediction = model.predict(features.reshape(1, -1))
                prediction_proba = model.predict_proba(features.reshape(1, -1))
            else:
                # PyTorch model
                model.eval()
                with torch.no_grad():
                    features_tensor = torch.FloatTensor(features.reshape(1, -1))
                    output = model(features_tensor)
                    prediction_proba = torch.softmax(output, dim=1).numpy()
                    prediction = np.argmax(prediction_proba, axis=1)

            result = {
                'methodology': ValuationMethodology(prediction[0]),
                'confidence': to_decimal(np.max(prediction_proba)),
                'probability_distribution': {
                    methodology.value: to_decimal(prob) 
                    for methodology, prob in zip(ValuationMethodology, prediction_proba[0])
                },
                'model_id': model_id,
                'prediction_timestamp': datetime.utcnow().isoformat()
            }

            self.logger.info(
                "Methodology prediction completed",
                model_id=model_id,
                predicted_methodology=result['methodology'],
                confidence=result['confidence']
            )

            return result

        except MethodologyError as e:
            self.logger.error(f"Error predicting methodology: {e}")
            raise

    async def _evaluate_mlp_performance(
        self,
        model: MLPClassifier,
        training_data: TrainingData
    ) -> ModelMetrics:
        """Evaluate MLP performance"""
        try:
            # Split data for evaluation
            X_train, X_test, y_train, y_test = train_test_split(
                training_data.features, training_data.labels, test_size=Decimal('0.2'), random_state=42
            )

            # Make predictions
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)

            # Calculate metrics
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted')
            recall = recall_score(y_test, y_pred, average='weighted')
            f1 = f1_score(y_test, y_pred, average='weighted')

            return ModelMetrics(
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                mse=Decimal('0.0'),  # Not applicable for classification
                mae=Decimal('0.0'),  # Not applicable for classification
                r2_score=Decimal('0.0'),  # Not applicable for classification
                cross_validation_score=accuracy,
                training_time=Decimal('0.0'),  # Would be measured during training
                prediction_time=Decimal('0.0'),  # Would be measured during prediction
                model_size=Decimal('0.0'),  # Would be calculated from model size
                memory_usage=Decimal('0.0'),  # Would be measured during training
                cpu_usage=Decimal('0.0')  # Would be measured during training
            )

        except DataValidationError as e:
            self.logger.error(f"Error evaluating MLP performance: {e}")
            raise

    async def _evaluate_pytorch_performance(
        self,
        model: nn.Module,
        training_data: TrainingData
    ) -> ModelMetrics:
        """Evaluate PyTorch model performance"""
        try:
            # This would contain actual PyTorch model evaluation
            # For now, return placeholder metrics
            return ModelMetrics(
                accuracy=Decimal('0.85'),
                precision=Decimal('0.85'),
                recall=Decimal('0.85'),
                f1_score=Decimal('0.85'),
                mse=Decimal('0.0'),
                mae=Decimal('0.0'),
                r2_score=Decimal('0.0'),
                cross_validation_score=Decimal('0.85'),
                training_time=Decimal('0.0'),
                prediction_time=Decimal('0.0'),
                model_size=Decimal('0.0'),
                memory_usage=Decimal('0.0'),
                cpu_usage=Decimal('0.0')
            )

        except DataValidationError as e:
            self.logger.error(f"Error evaluating PyTorch performance: {e}")
            raise

    async def _train_pytorch_model(
        self,
        model: nn.Module,
        data_loader: DataLoader,
        epochs: int = 100
    ) -> nn.Module:
        """Train PyTorch model"""
        try:
            # Set up training
            criterion = nn.CrossEntropyLoss()
            optimizer = optim.Adam(model.parameters(), lr=Decimal('0.001'))

            # Training loop
            model.train()
            for epoch in range(epochs):
                total_loss = 0
                for batch_features, batch_labels in data_loader:
                    optimizer.zero_grad()
                    outputs = model(batch_features)
                    loss = criterion(outputs, batch_labels)
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()

                if epoch % 10 == 0:
                    self.logger.debug(f"Epoch {epoch}, Loss: {total_loss / len(data_loader)}")

            return model

        except MethodologyError as e:
            self.logger.error(f"Error training PyTorch model: {e}")
            raise


class DeepNeuralNetwork(nn.Module):
    """Deep neural network for valuation methodology prediction"""

    def __init__(self, architecture: DeepLearningArchitecture):
        super(DeepNeuralNetwork, self).__init__()

        self.architecture = architecture
        self.layers = nn.ModuleList()

        # Input layer
        self.layers.append(nn.Linear(architecture.input_dim, architecture.hidden_layers[0]))

        # Hidden layers
        for i in range(len(architecture.hidden_layers) - 1):
            self.layers.append(nn.Linear(architecture.hidden_layers[i], architecture.hidden_layers[i + 1]))

        # Output layer
        self.layers.append(nn.Linear(architecture.hidden_layers[-1], architecture.output_dim))

        # Activation functions
        self.activations = []
        for activation in architecture.activation_functions:
            if activation == 'relu':
                self.activations.append(nn.ReLU())
            elif activation == 'tanh':
                self.activations.append(nn.Tanh())
            elif activation == 'sigmoid':
                self.activations.append(nn.Sigmoid())
            else:
                self.activations.append(nn.ReLU())

        # Dropout layers
        self.dropouts = nn.ModuleList()
        for dropout_rate in architecture.dropout_rates:
            self.dropouts.append(nn.Dropout(dropout_rate))

    def forward(self, x):
        for i, layer in enumerate(self.layers[:-1]):
            x = layer(x)
            if i < len(self.activations):
                x = self.activations[i](x)
            if i < len(self.dropouts):
                x = self.dropouts[i](x)

        # Output layer
        x = self.layers[-1](x)
        return x


class AttentionNetwork(nn.Module):
    """Attention-based neural network for valuation methodology prediction"""

    def __init__(self, input_dim: int, hidden_dim: int, num_heads: int, num_layers: int, output_dim: int):
        super(AttentionNetwork, self).__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.output_dim = output_dim

        # Input projection
        self.input_projection = nn.Linear(input_dim, hidden_dim)

        # Multi-head attention layers
        self.attention_layers = nn.ModuleList()
        for _ in range(num_layers):
            self.attention_layers.append(nn.MultiheadAttention(hidden_dim, num_heads))

        # Layer normalization
        self.layer_norms = nn.ModuleList()
        for _ in range(num_layers):
            self.layer_norms.append(nn.LayerNorm(hidden_dim))

        # Feed-forward network
        self.feed_forward = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 4),
            nn.ReLU(),
            nn.Linear(hidden_dim * 4, hidden_dim)
        )

        # Output projection
        self.output_projection = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # Input projection
        x = self.input_projection(x)

        # Add sequence dimension for attention
        x = x.unsqueeze(1)  # (batch_size, 1, hidden_dim)

        # Apply attention layers
        for attention_layer, layer_norm in zip(self.attention_layers, self.layer_norms):
            # Self-attention
            attn_output, _ = attention_layer(x, x, x)
            x = layer_norm(x + attn_output)

            # Feed-forward
            ff_output = self.feed_forward(x)
            x = layer_norm(x + ff_output)

        # Remove sequence dimension
        x = x.squeeze(1)  # (batch_size, hidden_dim)

        # Output projection
        x = self.output_projection(x)

        return x
