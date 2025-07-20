extends Node3D

@export var left_sprites: Array[Sprite3D] = []
@export var right_sprites: Array[Sprite3D] = []

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

func set_type(sprite: Sprite3D, type: Global.Type, index: int = 0):
	sprite.texture = load("res://sprites/pkm/" + Global.TYPE_TO_STRINGS[type][index])

func attack(sprite: Sprite3D, duration: float = 0.25):
	var tween = create_tween()
	tween.tween_property(sprite, "rotation_degrees:z", 45, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_property(sprite, "rotation_degrees:z", 0, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT).set_delay(duration)
	await tween.finished

func switch(sprite_a: Sprite3D, sprite_b: Sprite3D, duration: float = 1.5):
	var pos_a = sprite_a.global_position
	var pos_b = sprite_b.global_position
	var tween = create_tween()
	tween.tween_property(sprite_a, "global_position", pos_b, duration)
	tween.parallel().tween_property(sprite_b, "global_position", pos_a, duration)
	await tween.finished

func faint(sprite: Sprite3D, duration: float = 0.5):
	
	var tween = create_tween()
	tween.tween_property(sprite, "rotation_degrees:z", 90, duration).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tween.tween_interval(0.25)
	await tween.finished

func _input(event):
	if event.is_action_pressed("debug") and not _is_animating:
		_is_animating = true
		#attack(left_sprites[0])
		await attack(right_sprites[0])
		await left_sprites[0].get_child(0).set_health(40)
		await faint(left_sprites[0])
		await switch(left_sprites[0], left_sprites[2])
		_is_animating = false
