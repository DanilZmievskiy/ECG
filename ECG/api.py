from PIL import Image
import numpy as np
from typing import Tuple
from ECG.criterion_based_approach.pipeline import detect_risk_markers, diagnose, get_ste
from ECG.data_classes import Diagnosis, ElevatedST, RiskMarkers, Failed, \
    TextExplanation, TextAndImageExplanation
from ECG.digitization.preprocessing import adjust_image, binarization
from ECG.digitization.digitization import grid_detection, signal_extraction
import ECG.NN_based_approach.pipeline as NN_pipeline


###################
## convert image ##
###################

def convert_image_to_signal(image: Image.Image) -> np.ndarray or Failed:
    """This functions converts image with ECG signal to an array representation
    of the signal.

    Args:
        image (Image.Image): input image with ECG signal

    Returns:
        np.ndarray or Failed: array representation of ECG signal or Failed
    """
    try:
        image = np.asarray(image)
        adjusted_image = adjust_image(image)
        scale = grid_detection(adjusted_image)
        binary_image = binarization(adjusted_image)
        ecg_signal = signal_extraction(binary_image, scale)
        return ecg_signal
    except Exception as e:
        return Failed(reason='Failed to convert image to signal due to an internal error')


###################
## ST-elevation ###
###################

def check_ST_elevation(signal: np.ndarray, sampling_rate: int)\
        -> Tuple[ElevatedST, TextExplanation] or Failed:
    """This function checks for significant ST elevation using classic CV methods.

    Args:
        signal (np.ndarray): array representation of ECG signal
        sampling_rate (int): sampling rate

    Returns:
        Tuple[ElevatedST, TextExplanation] or Failed: a tuple of ST elevation evaluation
            and text explanation or Failed
    """
    elevation_threshold = 0.2

    try:
        ste_mV = get_ste(signal, sampling_rate)
        ste_bool = ste_mV > elevation_threshold

        ste_assessment = ElevatedST.Present if ste_bool else ElevatedST.Abscent

        explanation = 'ST elevation value in lead V3 (' + str(ste_mV) + ' mV)' \
            + (' did not exceed ', ' exceeded ')[ste_bool] + \
            'the threshold ' + str(elevation_threshold) + ', therefore ST elevation was'\
            + (' not detected.', ' detected.')[ste_bool]
        return (ste_assessment, TextExplanation(content=explanation))
    except Exception as e:
        return Failed(reason='Failed to assess ST elevation due to an internal error',
                      exception=e)


def check_ST_elevation_with_NN(signal: np.ndarray)\
        -> Tuple[ElevatedST, TextAndImageExplanation] or Failed:
    """This function checks for significant ST elevation using a NN.

    Args:
        signal (np.ndarray): array representation of ECG signal

    Returns:
        Tuple[ElevatedST, TextAndImageExplanation] or Failed:
            a tuple of ST elevation evaluation and explanation
            with text and GradCAM image or Failed
    """
    try:
        res, prob, gradcam = NN_pipeline.check_STE(signal)
        text_explanation = f'Significant ST elevation probability is {round(prob, 4)}'
        return (res, TextAndImageExplanation(text=text_explanation, image=gradcam))
    except Exception as e:
        return Failed(reason='Failed to assess ST elevation due to an internal error',
                      exception=e)


###################
## risk markers ###
###################

def evaluate_risk_markers(signal: np.ndarray, sampling_rate: int)\
        -> RiskMarkers or Failed:
    """This function evaluates MI risk markers.

    Args:
        signal (np.ndarray): array representation of ECG signal
        sampling_rate (int): sampling rate

    Returns:
        RiskMarkers or Failed: MI risk markers values or Failed
    """
    try:
        return detect_risk_markers(signal, sampling_rate)
    except Exception as e:
        return Failed(reason='Failed to evaluate risk markers due to an internal error',
                      exception=e)


###################
## diagnose #######
###################

def diagnose_with_risk_markers(signal: np.ndarray,
                               sampling_rate: int,
                               tuned: bool = False)\
        -> Tuple[Diagnosis, TextExplanation] or Failed:
    """This functions performs differential diagnostics of BER and MI on ECG signal
    that contains either of two. Uses formula based on MI risk marker values.

    Args:
        signal (np.ndarray): array representation of ECG signal
        sampling_rate (int): sampling rate
        tuned (bool, optional): True if you want to use formula tuned od CPSC 2018,
            otherwise False. Default is False

    Returns:
        Tuple[Diagnosis, TextExplanation] or Failed: a tuple with differential diagnosis
            (BER or MI) and text explanation or Failed
    """
    try:
        risk_markers = evaluate_risk_markers(signal, sampling_rate)

        stemi_diagnosis, stemi_criterion = diagnose(risk_markers, tuned)
        diagnosis_enum = Diagnosis.MI if stemi_diagnosis else Diagnosis.BER

        if tuned:
            formula = '(2.9 * [STE60 V3 in mm]) + (0.3 * [QTc in ms]) '\
                + '+ (-1.7 * np.minimum([RA V4 in mm], 19)) = '
            threshold = '126.9'
        else:
            formula = '(1.196 * [STE60 V3 in mm]) + (0.059 * [QTc in ms]) '\
                + '– (0.326 * [RA V4 in mm])) = '
            threshold = '23.4'

        explanation = 'Criterion value calculated as follows: ' + \
            formula + str(stemi_criterion) + \
            (' did not exceed ', ' exceeded ')[stemi_diagnosis] + \
            'the threshold ' + threshold + ', therefore the diagnosis is ' + \
            diagnosis_enum.value
        return (diagnosis_enum, TextExplanation(content=explanation))
    except Exception as e:
        return Failed(reason='Failed to diagnose due to an internal error', exception=e)


def check_BER_with_NN(signal: np.ndarray)\
        -> Tuple[bool, TextAndImageExplanation] or Failed:
    """This functions checks for BER on ECG signal with ST elevation. Uses a NN.

    Args:
        signal (np.ndarray): array representation of ECG signal

    Returns:
        Tuple[bool, TextAndImageExplanation] or Failed: a tuple containing boolean
            presence of BER and explanation with text and GradCAM image or Failed
    """
    try:
        res, prob, gradcam = NN_pipeline.is_BER(signal)
        text_explanation = f'BER probability is {round(prob, 4)}'
        return (res, TextAndImageExplanation(text=text_explanation, image=gradcam))
    except Exception as e:
        return Failed(reason='Failed to check for BER due to an internal error',
                      exception=e)


def check_MI_with_NN(signal: np.ndarray) -> Tuple[bool, TextExplanation] or Failed:
    """This functions checks for MI on ECG signal with ST elevation. Uses a NN.

    Args:
        signal (np.ndarray): array representation of ECG signal

    Returns:
        Tuple[bool, TextAndImageExplanation] or Failed: a tuple containing boolean
            presence of MI and explanation with text and GradCAM image or Failed
    """
    try:
        res, prob, gradcam = NN_pipeline.is_MI(signal)
        text_explanation = f'MI probability is {round(prob, 4)}'
        return (res, TextAndImageExplanation(text=text_explanation, image=gradcam))
    except Exception as e:
        return Failed(reason='Failed to check for MI due to an internal error',
                      exception=e)
