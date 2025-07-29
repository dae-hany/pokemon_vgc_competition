extends Node3D
class_name NetworkServer

var peer: PacketPeerUDP
var message_queue: Array = []

func _ready():
	peer = PacketPeerUDP.new()
	peer.bind(12345)
	print("UDP listening on port 12345")

func _process(_delta):
	while peer.get_available_packet_count() > 0:
		var array_bytes = peer.get_packet()
		var packet_string = array_bytes.get_string_from_utf8()
		
		var json = JSON.new()
		if json.parse(packet_string) == OK:
			message_queue.append(json.get_data())
			print("Queued message:", json.get_data())
		else:
			print("Invalid JSON:", packet_string)

func has_message() -> bool:
	return message_queue.size() > 0

func get_next_message() -> Dictionary:
	if has_message():
		return message_queue.pop_front()
	return {}
