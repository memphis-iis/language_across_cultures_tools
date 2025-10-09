import math
import cv2
import numpy as np
import xml.etree.ElementTree as ET

def calculate_distance(coord1, coord2):
    x1 = coord1[0]
    y1 = coord1[1]
    x2 = coord2[0]
    y2 = coord2[1]
    return [x1-x2, y1-y2]

def ResizeWithAspectRatio(image, width=None, height=None, inter=cv2.INTER_AREA):
    dim = None
    (h, w) = image.shape[:2]

    if width is None and height is None:
        return image
    if width is None:
        r = height / float(h)
        dim = (int(w * r), height)
    else:
        r = width / float(w)
        dim = (width, int(h * r))

    return cv2.resize(image, dim, interpolation=inter)

# Load the images
img_original = cv2.imread('images/voynichese/119.jpg', cv2.IMREAD_GRAYSCALE)
img_with_box = cv2.imread('images/voynichese/119.jpg', cv2.IMREAD_GRAYSCALE)
img_with_box = cv2.cvtColor(img_with_box, cv2.COLOR_GRAY2BGR)
img_template = cv2.imread('images/voynichese/f66r.jpg', cv2.IMREAD_GRAYSCALE)
num_columns = 3
num_rows = 10
count = 0

top_left = (0, 0)
top_right = (0, 0)
bottom_left = (0, 0)
bottom_right = (0, 0)

# load the XML file
xml_file = 'images/voynichese/voynichese-xml/f66r.xml'
tree = ET.parse(xml_file)
root = tree.getroot()
xml_data = {}

root_data = {"width": int(root.attrib['width']), "height": int(root.attrib['height'])}

for child in root:
    xml_data[child.attrib['index']] = {
        "x": int(child.attrib['x']),
        "y": int(child.attrib['y']),
        "width": int(child.attrib['width']),
        "height": int(child.attrib['height'])
    }

print(f"XML data loaded: {len(xml_data)} entries.")


if img_original is None or img_template is None:
    print("Error: Could not load one or both images.")
else:
    # Break the search image into smaller sections for better matching
    height, width = img_template.shape
    img_template_sections = []
    section_height = height // num_rows
    section_width = width // num_columns
    for i in range(num_rows):
        for j in range(num_columns):
            start_row = i * section_height
            end_row = (i + 1) * section_height if i < num_rows - 1 else height
            start_col = j * section_width
            end_col = (j + 1) * section_width if j < num_columns - 1 else width
            img_template_sections.append(img_template[start_row:end_row, start_col:end_col])
    print(f"Template image sections created: {len(img_template_sections)} sections.")

    # Iterate through each section of the template image
    for section in img_template_sections:
        count += 1
        # 1. Initialize SIFT Detector
        sift = cv2.SIFT_create()

        # 2. Find the keypoints and descriptors with SIFT
        kp1, des1 = sift.detectAndCompute(section, None)
        kp2, des2 = sift.detectAndCompute(img_original, None)

        # 3. Match keypoints using FLANN matcher
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)

        # 4. Filter good matches using Lowe's ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)

        # Minimum number of good matches to proceed
        MIN_MATCH_COUNT = 10
        print(f"Number of good matches: {len(good_matches)}")
        if len(good_matches) > MIN_MATCH_COUNT:
            # 5. Get coordinates of good matches
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

            # 6. Find the homography matrix
            # M is the transformation matrix; mask is for inliers/outliers
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            # Get the corners of the template image
            h, w = section.shape
            pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
            
            # print(f"Homography matrix:\n{M}")
            # print(f"Corners of the template image:\n{pts}")

            # 7. Project the corners onto the original image
            dst = cv2.perspectiveTransform(pts, M)

            top_left_template = calculate_distance(top_left, dst[0][0])
            top_right_template = calculate_distance(top_right, dst[3][0])
            bottom_left_template = calculate_distance(bottom_left, dst[1][0])
            bottom_right_template = calculate_distance(bottom_right, dst[2][0])

            if top_left[0] == 0 and top_left[1] == 0 and \
               top_right[0] == 0 and top_right[1] == 0 and \
               bottom_left[0] == 0 and bottom_left[1] == 0 and \
               bottom_right[0] == 0 and bottom_right[1] == 0:
                top_left = dst[0][0]
                bottom_left = dst[1][0]
                bottom_right = dst[2][0]
                top_right = dst[3][0]
            else: 
                right = False
                left = False
                up = False
                down = False
                sum_x = top_left_template[0] + top_right_template[0] + bottom_left_template[0] + bottom_right_template[0]
                sum_y = top_left_template[1] + top_right_template[1] + bottom_left_template[1] + bottom_right_template[1]

                avg_x = sum_x / 4
                avg_y = sum_y / 4

                # print(f"Average x: {avg_x}, Average y: {avg_y}")

                if -40 > avg_x or avg_x > 40:
                    if avg_x < 0:
                        # print("more to the right")
                        right = True
                    else:
                        # print("more to the left")
                        left = True

                if -40 > avg_y or avg_y > 40:
                    if avg_y < 0:
                        # print("more down")
                        down = True
                    else:
                        # print("more up")
                        up = True

                if right:
                    if up:
                        top_right = dst[3][0]
                    if down:
                        bottom_right = dst[2][0]
                    else:
                        top_right = dst[3][0]
                        bottom_right = dst[2][0]
                elif left:
                    if up:
                        top_left = dst[0][0]
                    if down:
                        bottom_left = dst[1][0]
                    else:
                        top_left = dst[0][0]
                        bottom_left = dst[1][0]

            # 8. Draw the bounding box on the original image
            # img_with_box = cv2.polylines(img_with_box, [np.int32(dst)], True, (0, 255, 0), 3, cv2.LINE_AA)
            print(f"Bounding box drawn on image {count}.")
    else:
        print(f"Not enough matches found - {len(good_matches)}/{MIN_MATCH_COUNT}")

# Adjust the coordinates to ensure they are within a reasonable range
top = top_left[1] - top_right[1]
bottom = bottom_left[1] - bottom_right[1]
left = top_left[0] - bottom_left[0]
right = top_right[0] - bottom_right[0]

# Top
print(f"-100 < {top} > 100" )
if -100 < top > 100:
    if top_left[1] < top_right[1]:
        top_right[1] = top_left[1]
    else:
        top_left[1] = top_right[1]

# Bottom
print(f"-100 < {bottom} > 100")
if -100 < bottom > 100:
    if bottom_left[1] > bottom_right[1]:
        bottom_right[1] = bottom_left[1]
    else:
        bottom_left[1] = bottom_right[1]

# Left
print(f"-100 < {left} > 100")
if -100 < left > 100:
    if top_left[0] < bottom_left[0]:
        bottom_left[0] = top_left[0]
    else:
        top_left[0] = bottom_left[0]

# Right
print(f"-100 < {right} > 100")
if -100 < right > 100:
    if top_right[0] < bottom_right[0]:
        bottom_right[0] = top_right[0]
    else:
        top_right[0] = bottom_right[0]

print("Final bounding box coordinates:")

print(f"Top left: {top_left}")
print(f"Top right: {top_right}")
print(f"Bottom left: {bottom_left}")
print(f"Bottom right: {bottom_right}")

original_width = img_original.shape[1]
original_height = img_original.shape[0]

template_width = img_template.shape[1]
template_height = img_template.shape[0]

xml_resolution_width = root_data["width"]
xml_resolution_height = root_data["height"]

print(f"XML resolution: {xml_resolution_width}x{xml_resolution_height}")
print(f"Template image size: {template_width}x{template_height}")
print(f"Cropped image size: {original_width}x{original_height}")

ratio_x = original_width / xml_resolution_width
ratio_y = original_height / xml_resolution_height
print(f"Ratio X: {ratio_x}, Ratio Y: {ratio_y}")

y_delta_x = bottom_left[0] - top_left[0]
y_delta_y = bottom_left[1] - top_left[1]

y_slope = y_delta_y / y_delta_x if y_delta_x != 0 else 0
print(f"Vertival: {y_slope}")

x_delta_x = top_right[0] - top_left[0]
x_delta_y = top_right[1] - top_left[1]

x_slope = x_delta_y / x_delta_x if x_delta_x != 0 else 0
print(f"Horizontal: {x_slope}")
# with top left as the reference point, skew the coordinates with angle

for key, value in xml_data.items():
    x = value["x"] * ratio_x + 50
    y = value["y"] * ratio_y
    width = value["width"] * ratio_x 
    height = value["height"] * ratio_y

    y_offset = width * x_slope
    x_offset = 0

    tl = (x, y)
    tr = (x + width, y + y_offset)
    bl = (x + x_offset, y + height)
    br = (x + width + x_offset, y + height + y_offset)

    # Transform the points based on the slopes


    # Draw the bounding box on the image
    img_with_box = cv2.polylines(img_with_box, [np.int32([tl, tr, br, bl])], True, (0, 255, 0), 3, cv2.LINE_AA)
    #print(f"XML entry {key} - x: {tl[0]}, y: {tl[1]}, width: {tr[0] - tl[0]}, height: {bl[1] - tl[1]}")

# Draw the min and max coordinates on the image
img_with_box = cv2.polylines(img_with_box, [np.int32([top_left, top_right, bottom_right, bottom_left])], True, (0, 0, 255), 3, cv2.LINE_AA)
# print(f"Bounding box coordinates: {top_left}, {top_right}, {bottom_right}, {bottom_left}")

# Display the result
img_with_box = ResizeWithAspectRatio(img_with_box, height=1000)
cv2.imshow('Matches', img_with_box)
cv2.waitKey(0)
cv2.destroyAllWindows()
cv2.imwrite("voynichese_result.jpg", img_with_box)