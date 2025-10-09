import cv2
import numpy as np
import matplotlib.pyplot as plt
from skimage.metrics import structural_similarity as ssim
from skimage.feature import hog
import cv2

base_path = "./images/base-cropped-bw.png"
sample_path = "./images/templates/2.png"

def resize_with_aspect_ratio(image, width=None, height=None, inter=cv2.INTER_AREA):
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

def display(image):
    image = resize_with_aspect_ratio(image, height=900)
    plt.imshow(image),plt.show()

def preprocess_image(image_path):
    # Read the input image
    image = cv2.imread(image_path)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    cleaned_image = cv2.adaptiveThreshold(
        gray, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 
        75, 10
    )
    # Use morphological operations to clean noise (optional)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2,2))
    cleaned_image = cv2.morphologyEx(cleaned_image, cv2.MORPH_OPEN, kernel)
    #cleaned_image = cv2.Canny(cleaned_image, threshold1=50, threshold2=150)
    return cleaned_image


cleaned_base = preprocess_image(base_path)
cleaned_template = preprocess_image(sample_path)
original_base = cv2.imread(base_path)

def skeletonize(image, size=(3, 3)):
    # Create a skeleton (empty image)
    skeleton = np.zeros(image.shape, np.uint8)

    # Use morphological operations to thin the image until the skeleton is extracted
    element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, size)
    done = False

    while not done:
        # Perform erosion and then dilation (opening)
        eroded = cv2.erode(image, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(image, temp)
        skeleton = cv2.bitwise_or(skeleton, temp)
        image = eroded.copy()

        # If no more changes, stop the loop
        if cv2.countNonZero(image) == 0:
            done = True

    return skeleton

def feature_matching(base, template):
    # Initiate SIFT detector
    sift = cv2.SIFT_create()
    
    # find the keypoints and descriptors with SIFT
    kp1, des1 = sift.detectAndCompute(template,None)
    kp2, des2 = sift.detectAndCompute(base,None)
    
    # BFMatcher with default params
    bf = cv2.BFMatcher()
    matches = bf.knnMatch(des1,des2,k=2)
    
    # Apply ratio test
    good = []
    for m,n in matches:
        print(m,n)
        if m.distance < 0.87*n.distance:
            good.append([m])
    
    # cv2.drawMatchesKnn expects list of lists as matches.
    img3 = cv2.drawMatchesKnn(template,kp1,base,kp2,good,None,flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
    
    display(img3)

def keypoint_detection(base, template):
    # Initialize ORB detector
    orb = cv2.ORB_create()

    # Detect keypoints and descriptors
    kp1, des1 = orb.detectAndCompute(template, None)  # Template (sample pen stroke)
    kp2, des2 = orb.detectAndCompute(base, None)  # base image
    # Create BFMatcher (Brute Force Matcher)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    # Match descriptors
    matches = bf.match(des1, des2)

    # Sort matches by distance
    matches = sorted(matches, key=lambda x: x.distance)

    # Draw matches
    result = cv2.drawMatches(template, kp1, base, kp2, matches[:10], None, flags=2)

    # Display the result
    display(result)

def skeletonize_match(base, sample):
    # base = preprocess_image(base)
    # sample = preprocess_image(sample)
    base = skeletonize(base, (3, 3))
    sample = skeletonize(sample, (3, 3))
    # Template matching to find the sample stroke in the document
    for contour in base:
        match_score = cv2.matchShapes(sample[0], contour, cv2.CONTOURS_MATCH_I1, 0.0)
        print(f"Match score: {match_score}")

        # If the match score is below a threshold, draw the contour
        if match_score < 0.4:  # Tune this threshold
            cv2.drawContours(original_base, [contour], -1, (0, 255, 0), 2)

    # Display the result
    display(original_base)

def contour_process(base, sample):
    base = cv2.imread(base)
    base = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    ret, base = cv2.threshold(base, 127, 255, 0)
    sample = cv2.imread(sample)
    sample = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    ret, sample = cv2.threshold(sample, 127, 255, 0)
    return base, sample

def contour_match(base, sample):
    # contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    contours_sample, _ = cv2.findContours(sample, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours_document, _ = cv2.findContours(base, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Compare the first contour of the sample to all contours in the document
    for contour in contours_document:
        match_score = cv2.matchShapes(contours_sample[0], contour, cv2.CONTOURS_MATCH_I1, 0.0)
        print(f"Match score: {match_score}")

        # If the match score is below a threshold, draw the contour
        if match_score < 0.04:  # Tune this threshold
            cv2.drawContours(original_base, [contour], -1, (0, 255, 0), 2)
    # cv2.drawContours(img, contours, -1, (0,255,0), 3)
    display(original_base)

base, sample = contour_process(base_path, sample_path)
skeletonize_match(base, sample)

# Save the output
# cv2.imwrite('output_image.jpg', matches)
