import unittest

try:
    from PIL import Image
    from knowthebigpicture.images import (
        InvalidGeneratedImage,
        validate_generated_image,
    )
except ImportError:
    Image = None
    InvalidGeneratedImage = None
    validate_generated_image = None


@unittest.skipUnless(Image is not None, "Pillow is not installed")
class ImageValidationTests(unittest.TestCase):
    def test_rejects_black_image(self):
        with self.assertRaisesRegex(InvalidGeneratedImage, "black"):
            validate_generated_image(Image.new("RGB", (1024, 1536), "black"))

    def test_rejects_blank_white_image(self):
        with self.assertRaisesRegex(InvalidGeneratedImage, "blank white"):
            validate_generated_image(Image.new("RGB", (1024, 1536), "white"))

    def test_rejects_tiny_image(self):
        with self.assertRaisesRegex(InvalidGeneratedImage, "dimensions"):
            validate_generated_image(Image.new("RGB", (64, 64), "gray"))

    def test_accepts_image_with_visual_detail(self):
        image = Image.new("RGB", (1024, 1536), "navy")
        for x in range(512, 1024):
            for y in range(1536):
                image.putpixel((x, y), (220, 180, 80))
        validate_generated_image(image)


if __name__ == "__main__":
    unittest.main()
