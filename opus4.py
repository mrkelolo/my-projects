import cv2
import numpy as np

class Opus4:
    """Placeholder Opus4 class for chart image analysis.

    This stub provides basic axis detection and data-point extraction when the
    external `opus4` package is not available.
    """

    def __init__(self, image, mode="high_resolution"):
        self.image = image
        self.mode = mode

    def axes(self):
        height, width = self.image.shape[:2]
        step_x = max(width // 10, 1)
        step_y = max(height // 10, 1)
        return {
            "x_axis": {
                "start": 0,
                "end": width,
                "step": step_x,
            },
            "y_axis": {
                "start": 0,
                "end": height,
                "step": step_y,
            },
        }

    def extract_data_points(self, axes):
        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        points = []

        for contour in contours:
            if cv2.contourArea(contour) < 50:
                continue
            moments = cv2.moments(contour)
            if moments["m00"] == 0:
                continue
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            points.append({"x": cx, "y": cy})

        if not points:
            points.append({"x": axes["x_axis"]["start"], "y": axes["y_axis"]["start"]})

        return points

    def structure_outputs(self, data_points):
        return [{"x": p["x"], "y": p["y"]} for p in data_points]
