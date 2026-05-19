class Config:

    def __init__(self):
        # Adjustable
        # self.THRESHOLD_PRE_GRADIENT = 4             # dribbble:4 rico:4 web:1
        # self.THRESHOLD_OBJ_MIN_AREA = 55            # bottom line 55 of small circle
        # self.THRESHOLD_BLOCK_GRADIENT = 5

        # *** Frozen ***
        self.THRESHOLD_REC_MIN_EVENNESS = 0.7
        self.THRESHOLD_REC_MAX_DENT_RATIO = 0.25
        self.THRESHOLD_LINE_THICKNESS = 8
        self.THRESHOLD_LINE_MIN_LENGTH = 0.95
        self.THRESHOLD_COMPO_MAX_SCALE = (0.25, 0.98)  # maximum height and width ratio
        self.THRESHOLD_TEXT_MAX_WORD_GAP = 10
        self.THRESHOLD_TEXT_MAX_HEIGHT = 0.04
        self.THRESHOLD_TOP_BOTTOM_BAR = (0.045, 0.94)
        self.THRESHOLD_BLOCK_MIN_HEIGHT = 0.03

        # Added COLOR mapping
        self.COLOR = {
            'Compo': (0, 255, 0),
            'Text': (0, 0, 255),
            'Block': (255, 0, 0),
            'Text Content': (255, 0, 255),
            'Icon': (255, 255, 0),
            'Image': (0, 255, 255)
        }
