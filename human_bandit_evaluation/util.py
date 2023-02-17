class Task:
    '''Defines the necessary components for each task entry.'''
    def __init__(self, category=None, sample_method=None, image_path=None,
                 attention_checks=None):
        # The category that the shown image belongs to.
        self.category = category
        # The method of sampling the next image, e.g. random, increasing_order,
        # None (in which case image_path is used).
        self.sample_method = sample_method
        # If specified, the image path overrides any other option.
        self.image_path = image_path
        # A list of lists of (question, answer) pairs used for performing
        # attention checks for this task.
        self.attention_checks = attention_checks
