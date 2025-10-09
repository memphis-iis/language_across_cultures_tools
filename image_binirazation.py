import cv2
from matplotlib import pyplot as plt
import numpy as np

img_grayscale = cv2.imread('./images/base.png', 0)
img = cv2.imread('./images/base.png')

def global_thresholding(): 
    _, global_threshold_200 = cv2.threshold(img_grayscale, 200, 255, cv2.THRESH_BINARY, )

    plt.figure(figsize = (15,15))
    titles = ["Threshold = 200"]
    for idx, thres in enumerate([global_threshold_200]):
        plt.subplot(1,3,idx+1)
        plt.imshow(thres, 'gray')
        plt.title(titles[idx])
        plt.xticks([]), plt.yticks([])

def adaptive_thresholding():
    adaptive_threshold_mean = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 5, 6)
    adaptive_threshold_gaussian = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 5, 6)

    plt.figure(figsize = (10,10))
    titles = ["Adaptive Threshold - Mean", "Adaptive Threshold - Gaussian"]
    for idx, thres in enumerate([adaptive_threshold_mean, adaptive_threshold_gaussian]):
        plt.subplot(1,2,idx+1)
        plt.imshow(thres, 'gray')
        plt.title(titles[idx])
        plt.xticks([]), plt.yticks([])

def otsu_thresholding(): 
    _, otsu_thresholding = cv2.threshold(img_grayscale, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    plt.imshow(otsu_thresholding, 'gray')

def kapur_thresholding(): 
    hist = cv2.calcHist([img_grayscale], [0], None, [500], [0, 256])
    prob = hist / float(img_grayscale.size)
    entropies = []

    for t in range(1, 255):
        w0 = np.sum(prob[:t])
        w1 = np.sum(prob[t:])

        if w0 == 0 or w1 == 0:
            continue

        h0 = -np.sum((prob[:t] / w0) * np.log((prob[:t] / w0) + 1e-10))
        h1 = -np.sum((prob[t:] / w1) * np.log((prob[t:] / w1) + 1e-10))

        entropies.append(h0 + h1)

    optimal_thresh = np.argmax(entropies)

    _, thresh_img = cv2.threshold(img_grayscale, optimal_thresh, 255, cv2.THRESH_BINARY)
    plt.imshow(thresh_img, 'gray')

kapur_thresholding()
plt.show()