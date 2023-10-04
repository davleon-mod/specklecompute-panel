"""
Common functions and classes for Modelical Dynamo Scripts
"""
import logging
import os
import json
import inspect


# <editor-fold desc="LOGGING">
def setup_logger(log_filename=None, log_base_path=None, log_filemode='w'):
    """

    :param str log_filename:
    :param object log_base_path: Path object
    :return: logging object
    """
    if not log_filename.endswith('.log'):
        log_filename = log_filename + '.log'
    folder = os.path.join(log_base_path, 'log')
    if not os.path.exists(folder):
        os.makedirs(folder)

    logfile = os.path.join(folder, log_filename)
    logging.basicConfig(filename=logfile,
                        filemode=log_filemode,
                        format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.DEBUG)

    logger = logging.getLogger(log_filename)
    return logger


# </editor-fold>
def json2dict(jsonfilepath):
    """
    Create python dict from json file

    :param str jsonfilepath: file path string
    :return: a Python dict
    """
    with open(jsonfilepath, 'r') as json_file:
        return json.load(json_file)


def dict2json(jsonout, d2json):
    """Creates json file from python dictionary

    This is a docstring in Google format

    Args:
        jsonout:
        d2json:

    Returns:
        None: Side effect, creates json file from dict

    Examples:

        dict2json('c:\\1_Temporal\\test_file.json', pydict)
    """
    with open(jsonout, 'w+') as jsf:
        json.dump(d2json, jsf)
    # ensure_ascii=True escapa los caracteres unicode \ux0xff etc...
    # json.dump(d2json, jsf, ensure_ascii=False, encoding="utf-8")


def initialize_logger(log_filepath):
    """Initialize a logger object for debugging purposes.


    Args:
        log_filepath (str): The absolute path to where the log file will be created

    Returns:
        Logger: A formatted Logger object from logging module
    """
    log = logging.getLogger('DebugLog')
    log.setLevel(logging.NOTSET)
    handler = logging.FileHandler(log_filepath,mode='w')
    fmt = logging.Formatter('%(message)s')
    handler.setFormatter(fmt)
    log.addHandler(handler)
    log.info('----')
    log.info('Debug Logging')
    log.info('----')
    return log


def inspect_object(object):
    """ Logs all the attributes of a class for debugging purposes. """
    attrs = inspect.getmembers(object)
    msg = "\n"
    msg += "-----------------------------Logging attributes for {}".format(str(object))
    msg += "\n ".join(str(item) for item in attrs)
    msg += "\n"
    return msg