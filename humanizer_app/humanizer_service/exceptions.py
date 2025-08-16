# humanizer_app/humanizer_service/exceptions.py

class AllModelsFailedError(Exception):
    """Custom exception raised when all OpenAI models in the fallback list fail."""
    def __init__(self, message="We're sorry, but we were unable to process your request at this time. Please try again later.", debug_info="All OpenAI models failed to generate a response."):
        self.message = message      # Safe message for the client
        self.debug_info = debug_info  # Detailed info for server logs
        super().__init__(self.debug_info)

class CustomApiError(Exception):
    """Custom exception for failures related to a third-party API."""
    def __init__(self, message="Humanizer Error. Please try again or contact support if the problem persists.", debug_info="The third-party humanizer API failed."):
        self.message = message      # Safe message for the client
        self.debug_info = debug_info  # Detailed info for server logs
        super().__init__(self.debug_info)
