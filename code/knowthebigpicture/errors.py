class KtwError(RuntimeError):
    """User-facing error that should be printed without a traceback."""


class VerificationError(KtwError):
    """A generated explainer failed mechanical verification."""


class InsufficientSourceError(KtwError):
    """The available material cannot support a grounded explanation."""


class ImagePolicyError(KtwError):
    """The image provider refused a prompt for content-policy reasons."""
