from kivy.uix.button import Button
from kivy.uix.label import Label


class WrappedLabel(Label):
    """Kivy label with wrapped text

    From https://stackoverflow.com/a/58227983/40916
    by Ferd and Tshirtman
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            width=lambda *x: self.setter("text_size")(self, (self.width, None)),
            texture_size=lambda *x: self.setter("height")(self, self.texture_size[1]),
        )


class WrappedButton(Button):
    """Kivy button with wrapped text

    Based on WrappedLabel
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            width=lambda *x: self.setter("text_size")(self, (self.width, None)),
            texture_size=lambda *x: self.setter("height")(self, self.texture_size[1]),
        )
