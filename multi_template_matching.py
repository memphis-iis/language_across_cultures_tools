import cv2
import numpy as np
import os
from MTM import matchTemplates, drawBoxesOnRGB
import matplotlib.pyplot as plt

listTemplate = []
image_folder = "./images/voynichese"
template_img = cv2.imread(os.path.join(image_folder, "f66r.jpg"))
template_img = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
listTemplate.append(("f66r", template_img))

input_img = cv2.imread(os.path.join("./images/voynichese", "119.jpg"))
input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2GRAY)
hits = matchTemplates(listTemplate,
                      input_img,
                      score_threshold=0.9,
                      method=cv2.TM_CCOEFF_NORMED,
                      maxOverlap=0.25)

print(hits)

overlay = drawBoxesOnRGB(input_img,
                         hits,
                         showLabel = True,
                         labelColor=(255, 0, 0),
                         boxColor = (0, 0, 255),
                         labelScale=1,
                         boxThickness = 3)

plt.imshow(overlay)
plt.show()