extends ColorRect
class_name FadeScreen

var _is_fading = false

func _ready():
	color.a = 1.0

func is_faded_out() -> bool:
	return color.a > 0.0

func _target_alpha() -> float:
	return 0.0 if is_faded_out() else 1.0

func fade_out_in(duration: float = 1.0):
	var tween = create_tween()
	tween.tween_property(self, "color:a", _target_alpha(), duration).set_trans(Tween.TRANS_LINEAR).set_ease(Tween.EASE_IN_OUT)
	await tween.finished

func _input(event):
	if event.is_action_pressed("debug2") and not _is_fading:
		print('fade')
		_is_fading = true
		fade_out_in()
		_is_fading = false
		print('fade out')
