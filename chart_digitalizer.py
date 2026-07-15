# Import required libraries
import os
import sys
import cv2
import numpy as np
import pandas as pd
from opus4 import Opus4


def load_image(image_path):
    image_path = os.path.abspath(image_path)
    if not os.path.isfile(image_path):
        print(f"Error: Image file not found: {image_path}")
        print("Please place the chart image in the project folder or pass a valid image file path.")
        sys.exit(1)

    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Invalid image path or unsupported image format: {image_path}")
        sys.exit(1)

    return image


image_path = sys.argv[1] if len(sys.argv) > 1 else "test_chart_image.png"
image = load_image(image_path)

# Create an Opus4 instance with high-resolution vision capabilities
opus4 = Opus4(image, mode="high_resolution")

# Identify the axes in the chart
axes = opus4.axes()
print("Axes:")
print(axes)

# Expected output data structure for opus4.axes():
# {
#     "x_axis": {
#         "start": 10,
#         "end": 100,
#         "step": 10
#     },
#     "y_axis": {
#         "start": 0,
#         "end": 100,
#         "step": 10
#     }
# }

# Extract the data points from the chart
data_points = opus4.extract_data_points(axes)
print("Data Points:")
print(data_points)

# Expected output data structure for opus4.extract_data_points():
# [
#     {"x": 10, "y": 20},
#     {"x": 20, "y": 30},
#     {"x": 30, "y": 40},
#    ...
# ]

# Structure the model outputs using tools
structured_data = opus4.structure_outputs(data_points)
print("Structured Data:")
print(structured_data)

# Save the extracted data to a Pandas DataFrame
df = pd.DataFrame(structured_data)
df.to_csv("extracted_data.csv", index=False)

# Display the chart with the extracted data points
cv2.imshow("Chart with Extracted Data Points", image)
cv2.waitKey(0)
cv2.destroyAllWindows()