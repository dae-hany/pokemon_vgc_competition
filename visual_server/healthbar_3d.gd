extends Sprite3D

@onready var health_bar = $SubViewport/TextureProgressBar

# var _is_animating = false

func _ready() -> void:
	texture = $SubViewport.get_texture()

func set_health(value: float):
	var tween = create_tween()
	tween.tween_property(health_bar, "value", clamp(value, 0, health_bar.max_value), 1.0) \
			.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	await tween.finished

#func _input(event):
#   _is_animating = true
#	if event.is_action_pressed("debug") and not _is_animating:
#		set_health(40)
#   _is_animating = false
