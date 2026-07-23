class KttError(RuntimeError):
    """User-facing error that should be printed without a traceback."""


class VerificationError(KttError):
    """A generated timeline failed mechanical verification."""


class InsufficientSourceError(KttError):
    """The source text did not contain enough dated facts to build a timeline."""


class ImagePolicyError(KttError):
    """The image provider refused a prompt for content-policy reasons."""
