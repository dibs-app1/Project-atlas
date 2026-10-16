"""Flash limiter: no frame may change the average brightness by more than LIMIT (0-255) from the frame before.
If something sweeps across the camera (a tree, a house, a passing train), the change is eased in over a few
frames instead. QA's flash check uses the same measure, with a limit of 12."""
import numpy as np
from PIL import Image

LIMIT = 8.0


class FlashGuard:
    def __init__(self, limit=LIMIT):
        self.prev = None
        self.limit = limit

    @staticmethod
    def luma(a):
        return float((a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114)[::8, ::8].mean())

    def __call__(self, img):
        a = np.asarray(img.convert("RGB"), np.float32)
        if self.prev is not None:
            y0, y1 = self.luma(self.prev), self.luma(a)
            d = abs(y1 - y0)
            if d > self.limit:
                k = self.limit / d
                a = self.prev * (1 - k) + a * k
        self.prev = a
        return Image.fromarray(a.clip(0, 255).astype(np.uint8))
