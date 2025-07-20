extends TextureProgressBar

@onready var bar_green = preload("res://sprites/barHorizontal_green_mid 200.png")
@onready var bar_yellow = preload("res://sprites/barHorizontal_yellow_mid 200.png")
@onready var bar_red = preload("res://sprites/barHorizontal_red_mid 200.png")

func _ready() -> void:
    show()

func _process(delta: float) -> void:
    texture_progress = bar_green
    if value < 0.5 * max_value:
        texture_progress = bar_yellow
    if value < 0.25 * max_value:
        texture_progress = bar_red