import os
from PIL import Image


# Directory containing PNG images
directory = '/Users/leonardo/Desktop/Tesi/LTSBikePlan/images/Trento/versionipngdihtml'

# Desired resolution
new_width = 800
new_height = 600

for filename in os.listdir(directory):
    if filename.endswith(".png"):
        file_path = os.path.join(directory, filename)
        with Image.open(file_path) as img:
            # Resize the image
            img = img.resize((new_width, new_height), Image.ANTIALIAS)
            # Save the image back to the directory
            img.save(file_path)

print("All PNG images have been resized.")


