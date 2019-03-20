#!/usr/bin/env python

"""
    Author: Pengjia Zhu (zhupengjia@gmail.com)
"""


class SkillBase:
    """
        Base skill class. Define some necessaryy methods for a skill
    """
   
    def __getitem__(self, response):
        """
            convert response string to value
        """
        return None

    def init_model(self, **args):
        """
            model initialization, used for getting response
        """

    def update_mask(self, current_status):
        """
            Update response masks after retrieving utterance and before getting response
            
            Input:
                - current_status: dictionary of status, generated from Dialog_Status module
        """
        return None

    def get_response(self, current_status):
        """
            predict response value from current status

            Input:
                - current_status: dictionary of status, generated from Dialog_Status module
        """
        return None

    def update_response(self, response, current_status):
        """
            update current response to the response status.
            
            Input:
                - response: value of response
                - current_status: dictionary of status, generated from Dialog_Status module
        """
        return current_status
