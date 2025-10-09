# trying to use gabor filters for image processing
import cv2
import numpy as np
from matplotlib import pyplot as plt

theta = [0, 23, 45, 68, 90, 113, 135, 158]
gamma = [1, 2, 3]

"""
Sigma: Standard deviation of the Gaussian envelope.
Theta: Orientation of the normal to the parallel stripes of a Gabor function.
Lambda: Wavelength of the sinusoidal factor.
Gamma: Spatial aspect ratio.
Psi: Phase offset.
ktype: Type of the filter coefficients.
"""
def gabor_filters(img, kernel_size=31, sigma=4.0, theta=0, lambd=10.0, gamma=2, psi=0, ktype=cv2.CV_32F):
    """Apply Gabor filters to the image."""
    kernel = cv2.getGaborKernel((kernel_size, kernel_size), sigma, theta, lambd, gamma, psi, ktype)
    filtered_img = cv2.filter2D(img, cv2.CV_8UC3, kernel)
    return filtered_img

def find_match_gabor(img, template, kernel_size=31, sigma=4.0, theta=0, lambd=10.0, gamma=2, psi=0):
    """Find the best match of the template in the image using Gabor filters."""
    filtered_img = gabor_filters(img, kernel_size, sigma, theta, lambd, gamma, psi)
    result = cv2.matchTemplate(filtered_img, template, cv2.TM_CCOEFF_NORMED)
    return result

def main():
    img = cv2.imread('./images/templates/1.png', 0)
    img2 = cv2.imread('./images/templates/2.png', 0)
    max_match_value = 0
    max_match_theta = 0
    max_match_gamma = 0
    # images = [img, img2]
    # plt.figure(figsize=(15, 15))


    # for i, t in enumerate(theta):
    #     for j, g in enumerate(gamma):
    #         for k, im in enumerate(images):
    #             # Apply Gabor filter
    #             filtered_img = gabor_filters(im, theta=np.deg2rad(t), gamma=g)
    #             plt.subplot(len(theta), len(gamma) * 2, i * len(gamma) + j + 1 + k * len(theta) * len(gamma))
    #             plt.imshow(filtered_img, cmap='gray')
    #             plt.title(f'Theta: {t}°, Gamma: {g}, Image: {k+1}')
    #             plt.xticks([]), plt.yticks([])

    # plt.tight_layout()
    # plt.show()
    for i, t in enumerate(theta):
        for j, g in enumerate(gamma):
            result = find_match_gabor(img, img2, kernel_size=31, sigma=4.0, theta=np.deg2rad(t), lambd=10.0, gamma=g, psi=0)
            print(f'Theta: {t}°, Gamma: {g}, Max Match Value: {np.max(result)}')
            if np.max(result) > max_match_value:
                max_match_value = np.max(result)
                max_match_theta = t
                max_match_gamma = g

    print(f'Best Match - Theta: {max_match_theta}°, Gamma: {max_match_gamma}, Max Match Value: {max_match_value}')
    best_match_result = gabor_filters(img, kernel_size=31, sigma=4.0, theta=np.deg2rad(max_match_theta), lambd=10.0, gamma=max_match_gamma, psi=0)
    plt.subplot(1, 2, 1)
    plt.imshow(best_match_result, cmap='gray')
    plt.title(f'Best Match - Theta: {max_match_theta}°, Gamma: {max_match_gamma}')
    best_match_result_template = gabor_filters(img2, kernel_size=31, sigma=4.0, theta=np.deg2rad(max_match_theta), lambd=10.0, gamma=max_match_gamma, psi=0)
    plt.subplot(1, 2, 2)
    plt.imshow(best_match_result_template, cmap='gray')
    plt.title('Template Image with Best Match')
    plt.xticks([]), plt.yticks([])
    plt.show()

if __name__ == "__main__":
    main()