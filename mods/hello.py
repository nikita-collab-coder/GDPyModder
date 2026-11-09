# Example: messages and your own popup (F1).
import gd

NAME = "Hello"
VERSION = "1.3"
AUTHOR = "PyModder"
DESCRIPTION = "Example mod: messages in a level, a popup on F1 and a button on the level page."


@gd.on_level_start
def start(level):
    gd.notify(f"Good luck on {level.name}!")


@gd.on_complete
def done(level):
    gd.notify(f"Beaten in {level.attempts} attempts!", 4, color=(120, 255, 120))


@gd.on_key("F1")
def window():
    p = gd.Popup("Hello!")
    p.text("This popup is made in Python.\nClose it with ESC or the X.")
    name = p.input(placeholder="What is your name?")

    def ok():
        p.close()
        gd.notify(f"Hi, {name.text or 'player'}!")
    p.button("OK", ok)
    p.show()


@gd.level_button(text="Hi", position="bottom-right")    # a button on the page of every online level
def level_page(layer, level):
    gd.notify(f"{level.name} by {level.creator}: {level.downloads} downloads")
