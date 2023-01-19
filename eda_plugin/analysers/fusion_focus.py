import numpy as np
from skimage.exposure import equalize_hist
from skimage.measure import label
from skimage.measure import regionprops
from skimage.morphology import remove_small_objects
from eda_plugin.utility.qt_classes import QWidgetRestore

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5 import QtWidgets
import qdarkstyle


def __threshold(image:np.array, mask:np.array=None, percentile:float=99):
    """Set the background level and remove.

    Args:
      image: An input image of type np.arrayr.
      mask: A mask indicating where the image should be calculated.
      percentile: The threshold for the background.
    Returns:
      image: An output image with background removed.
    """
    if mask is None:
        mask = np.ones(image.shape)
    values = (image*mask).flatten()
    values = values[values>0]
    threshold = np.percentile(values, percentile)
    image[image<threshold] = 0
    return image

def __normolize(image:np.array):
    """Normalize the value of the image to be between 0-1.
    Args:
      image: An input image of type np.array.
    Returns:
      image: An output image with value between 0-1.
    """
    mask = image!=0
    values = image.flatten()
    values = values[values>0]
    vmax = np.max(values)
    vmin = np.min(values)
    if vmax != vmin:
        image = (image-vmin)/(vmax-vmin)
    return image*mask

def __equalize(image:np.array):
    """Perform histogram equalization on the image.
    Args:
      image: An input image of type np.array.
    Returns:
      image: An output image equalized.
    """
    image = equalize_hist(image, nbins=256, mask = image>0)
    return image

def __convolve(image:np.array, window:np.array = np.ones((3, 3))):
    """Perform  2D convolution on the image.
    Args:
      image: An input image of type np.array.
      window: An filter of type np.arrayr. Noet: The length of the filter needs to be an odd number
    Returns:
      image_p: An output image convd.
    """
    s = window.shape + tuple(np.subtract(image.shape, window.shape) + 1)
    strd = np.lib.stride_tricks.as_strided
    subM = strd(image, shape = s, strides = image.strides * 2)
    image_p = np.einsum('ij,ijkl->kl', window, subM)
    image_p = np.pad(image_p, int((window.shape[0]-1)/2),constant_values=0)
    return image_p

def preprocess(image:np.array, percentile:float=99):
    """Image preprocessing flow.
    Args:
      image: An input image of type np.array.
      percentile: The threshold for the background.
    Returns:
      c: An output image preprocessed.
      mask: A mask indicating where the image should be calculated.
    """
    a = __threshold(image, percentile=percentile)
    b = __normolize(a)
    c = __equalize(b)
    mask = b>0
    return c, mask

def detct_focus(image:np.array, mask:np.array, times:int=3, window:np.array = np.ones((3,3)), percentile:float=50):
    """The detection process of the fusion point.
    Args:
      image: An input image of type np.array.
      mask: A mask indicating where the image should be calculated.
      times: The number of deeps to perform the convolution.
      window: An filter of type np.arrayr. Noet: The length of the filter needs to be an odd number.
      percentile: Threshold for retaining possible points for next iteration.
    Returns:
      image: An output image with detected regions.
      
    """
    for i in range(0, times):
        a = __convolve(image, window)
        b = __threshold(a, mask, percentile=percentile)
        c = __normolize(b)
        d = __equalize(c)
        mask = c>0
        image = d*mask
    return image

def label_regions(image:np.array, min_size:int=5):
    """Convert image to label.
    Args:
      image: An input image of type np.array.
      min_size: The minimum area of ​​the detected area to keep.
    Returns:
      b_image: An output labeled image.
    """
    b_image = label(image>0, background=0, connectivity=1)
    regions = regionprops(b_image)
    areas = np.array([x.area for x in regions])
    if len(areas)>3:
        min_size = max(min_size,np.percentile(areas, 10))
        b_image = remove_small_objects(b_image, min_size)
    return b_image

def sort_regions(image:np.array, mask:np.array):
    """Sort the detected regions  by intensity.
    Args:
      image: An input image of type np.array.
      mask: A mask indicating where the image should be calculated.
    Returns:
      results: The coordinate information of the detected area.
    """
    regions = regionprops(mask)
    results = np.zeros((3, len(regions)))
    for i in range(0, len(regions)):
        label = regions[i].label
        value = (image*(mask == label)).flatten()
        results[0, i] = np.percentile(value[value>0], 95)
        results[1:, i] = np.array(regions[i].centroid, dtype=np.int_)
    return results[1:, np.argsort(-results[0,:])]

def pipeline(image:np.array, background_percentile:float = 99, times:int = 3, foodprint:np.array = np.ones((3, 3)), filter_percentile:float = 50):
    """Fusion point detection process.
    Args:
      image: An input image of type np.array.
      background_percentile: The threshold for the background.
      times: The number of deeps to perform the convolution.
      foodprint: An filter of type np.array. Noet: The length of the filter needs to be an odd number.
      filter_percentile: Threshold for retaining possible points for next iteration.
    Returns:
      centers: The coordinate information of the detected area.
    """
    pred_image, mask = preprocess(image.copy(), percentile=background_percentile)
    detected = detct_focus(pred_image.copy(), mask=mask, times = times, window=foodprint, percentile=filter_percentile)
    label_detected = label_regions(detected.copy())
    centers = sort_regions(detected, label_detected)
    return centers


class My_GUI(QWidgetRestore):
  """GUI for input/update of the parameters used for a change between two frame rates."""

  new_parameters = pyqtSignal(object)

  def __init__(self):
      """Set up the PyQt GUI with all the parameters needed for interpretation."""
      super().__init__()

      self.slow_interval_input = QtWidgets.QLineEdit()

      param_layout = QtWidgets.QFormLayout(self)
      param_layout.addRow("Wanlans value", self.slow_interval_input)

      self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))
