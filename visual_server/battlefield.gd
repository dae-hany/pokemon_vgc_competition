extends Node3D

@export var left_sprites: Array[Node3D] = []
@export var right_sprites: Array[Node3D] = []

var _is_animating = false

func _ready():
	set_type(left_sprites[0], Global.Type.BUG)
	set_type(left_sprites[1], Global.Type.FIRE)
	set_type(left_sprites[2], Global.Type.FLYING)
	set_type(left_sprites[3], Global.Type.WATER)
	set_type(right_sprites[0], Global.Type.PSYCHIC)
	set_type(right_sprites[1], Global.Type.NORMAL)
	set_type(right_sprites[2], Global.Type.DARK)
	set_type(right_sprites[3], Global.Type.ROCK)

func set_type(sprite: Node3D, type: Global.Type, index: int = 0):
	sprite.get_child(0).texture = load("res://sprites/pkm/" + Global.TYPE_TO_STRINGS[type][index])

func attack(sprite: Node3D, duration: float = 0.25):
	Global.text_box.show_message("Perform attack!")
	await Global.text_box.text_finished
	var tween = create_tween()
	tween.tween_property(sprite.get_child(0), "rotation_degrees:z", 45, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_property(sprite.get_child(0), "rotation_degrees:z", 0, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT).set_delay(duration)
	await tween.finished

func switch(sprite_a: Node3D, sprite_b: Node3D, duration: float = 1.5):
	Global.text_box.show_message("Switch!")
	await Global.text_box.text_finished
	var pos_a = sprite_a.global_position
	var pos_b = sprite_b.global_position
	var tween = create_tween()
	tween.tween_property(sprite_a, "global_position", pos_b, duration)
	tween.parallel().tween_property(sprite_b, "global_position", pos_a, duration)
	await tween.finished

func damage(sprite: Node3D, offset := 0.05, duration := 0.05, shakes := 6):
	var tween = create_tween()
	var original_pos = sprite.get_child(0).position  # local position
	for i in range(shakes):
		var dir = -1 if i % 2 == 0 else 1
		var target_pos = original_pos + Vector3(offset * dir, 0, 0)
		tween.tween_property(sprite.get_child(0), "position", target_pos, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	# Return to original position smoothly
	tween.tween_property(sprite.get_child(0), "position", original_pos, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	await tween.finished
	Global.text_box.show_message("Took damage!")
	await Global.text_box.text_finished

func faint(sprite: Node3D, duration: float = 0.5):
	Global.text_box.show_message("Fainted!")
	await Global.text_box.text_finished
	var tween = create_tween()
	tween.tween_property(sprite.get_child(0), "rotation_degrees:z", 90, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_interval(0.1)
	await tween.finished

func _input(event):
	if event.is_action_pressed("debug") and not _is_animating:
		_is_animating = true
		#attack(left_sprites[0])
		await attack(right_sprites[0], 0.1)
		await damage(left_sprites[0])
		await left_sprites[0].get_child(1).set_health(40)
		await faint(left_sprites[0], 0.2)
		await switch(left_sprites[0], left_sprites[2], 0.5)
		_is_animating = false
