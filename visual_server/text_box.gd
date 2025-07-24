extends Label

var full_text := ""
var current_index := 0
var char_delay := 0.04 # seconds per character
var typing := false

signal text_finished

func _ready():
    Global.text_box = self
    text = ""
    hide()
    show_message("Welcome Trainer! This is your first battle.")

func show_message(_text: String, delay := 0.04):
    full_text = _text
    char_delay = delay
    current_index = 0
    text = ""
    show()
    typing = true
    start_typing()

func start_typing():
    # Start typing coroutine
    await _type_text()

func _type_text() -> void:
    while current_index < full_text.length():
        text += full_text[current_index]
        current_index += 1
        await get_tree().create_timer(char_delay).timeout
    typing = false
    emit_signal("text_finished")
