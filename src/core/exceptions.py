class ApexQuantException(Exception):
    """Base exception for all ApexQuant errors."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ExchangeConnectionError(ApexQuantException):
    """Raised when connecting or writing to an exchange API fails."""
    pass


class OrderExecutionError(ApexQuantException):
    """Raised when an order placement, modification, or cancellation fails."""
    def __init__(self, message: str, order_details: dict = None):
        super().__init__(message)
        self.order_details = order_details or {}


class RiskLimitExceeded(ApexQuantException):
    """Raised when a trading operation breaches one of the active risk guardrails."""
    def __init__(self, message: str, limit_type: str = "general"):
        super().__init__(message)
        self.limit_type = limit_type


class StrategyInitializationError(ApexQuantException):
    """Raised when starting or configuring a strategy goes wrong."""
    pass


class DatabaseOperationError(ApexQuantException):
    """Raised when writing or reading from database layer fails."""
    pass


class EncryptionError(ApexQuantException):
    """Raised when encrypting or decrypting sensitive credentials fails."""
    pass
