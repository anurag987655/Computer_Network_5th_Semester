import json
import sys
import hashlib
import bencodepy
import requests
import struct
import socket
import math


def decode_bencode(bencoded_value):
    def decode_string(data, index):
        colon_index = data.find(b':', index)
        length = int(data[index:colon_index])
        start = colon_index + 1
        end = start + length
        return data[start:end], end

    def decode_integer(data, index):
        end_index = data.find(b'e', index)
        number = int(data[index + 1:end_index])
        return number, end_index + 1

    def decode_list(data, index):
        result = []
        index += 1  # Skip the 'l'
        while data[index] != ord(b'e'):
            value, index = decode(data, index)
            result.append(value)
        return result, index + 1  # Skip the 'e'

    def decode_dictionary(data, index):
        result = {}
        index += 1  # Skip the 'd'
        while data[index] != ord(b'e'):
            key, index = decode_string(data, index)  # Dictionary keys are always strings
            value, index = decode(data, index)
            result[key.decode('utf-8', errors='replace')] = value
        return result, index + 1  # Skip the 'e'

    def decode(data, index):
        if chr(data[index]).isdigit():
            return decode_string(data, index)
        elif data[index] == ord('i'):
            return decode_integer(data, index)
        elif data[index] == ord('l'):
            return decode_list(data, index)
        elif data[index] == ord('d'):
            return decode_dictionary(data, index)
        else:
            raise ValueError(f"Invalid bencoded value at index {index}")

    decoded_value, _ = decode(bencoded_value, 0)
    return decoded_value


def bytes_to_str(data):
    if isinstance(data, bytes):
        return data.decode(errors='replace')
    elif isinstance(data, list):
        return [bytes_to_str(item) for item in data]
    elif isinstance(data, dict):
        return {key: bytes_to_str(value) for key, value in data.items()}
    else:
        return data


def extract_info_hash(bencoded_value):
    _, bencoded_value_from_info = bencoded_value.split(b"info")
    _, dict_length = decode_bencode(bencoded_value_from_info)
    return bencoded_value_from_info[:dict_length]


def extract_pieces_hashes(pieces_hashes):
    index, result = 0, []
    while index < len(pieces_hashes):
        result.append(pieces_hashes[index: index + 20].hex())
        index += 20
    return result


def get_peers(decoded_data, info_hash):
    params = {
        "info_hash": info_hash,
        "peer_id": "00112233445566778899",
        "port": 6881,
        "uploaded": 0,
        "downloaded": 0,
        "left": decoded_data["info"].get("length", 0),
        "compact": 1,
    }
    response = requests.get(decoded_data["announce"].decode(), params=params)
    return decode_peers(decode_bencode(response.content).get("peers", b""))


def decode_peers(peers):
    index, result = 0, []
    while index < len(peers):
        ip = ".".join(str(b) for b in peers[index: index + 4])
        port = struct.unpack("!H", peers[index + 4: index + 6])[0]
        result.append(f"{ip}:{port}")
        index += 6
    return result


def receive_message(sock):
    length = sock.recv(4)
    while not length or not int.from_bytes(length, byteorder='big'):
        length = sock.recv(4)
    message = sock.recv(int.from_bytes(length, byteorder='big'))
    while len(message) < int.from_bytes(length, byteorder='big'):
        message += sock.recv(int.from_bytes(length, byteorder='big') - len(message))
    return length + message


def download_file(decoded_data, info_hash, output_file):
    piece_length = decoded_data["info"].get("piece length", 0)
    file_length = decoded_data["info"].get("length", 0)
    pieces_hashes = decoded_data["info"]["pieces"]

    total_number_of_pieces = len(pieces_hashes) // 20

    # Collect all the pieces
    pieces_data = bytearray()
    for piece_index in range(total_number_of_pieces):
        print(f"Downloading piece {piece_index}...")
        piece_data = download_piece(decoded_data, info_hash, piece_index)
        if not piece_data:
            print(f"Failed to download piece {piece_index}")
            return
        # Append the piece data
        pieces_data.extend(piece_data)

    # Verify integrity
    for piece_index in range(total_number_of_pieces):
        start = piece_index * piece_length
        end = start + piece_length
        if piece_index == total_number_of_pieces - 1:
            end = file_length

        piece_data = pieces_data[start:end]
        expected_hash = pieces_hashes[piece_index * 20: (piece_index + 1) * 20]
        if hashlib.sha1(piece_data).digest() != expected_hash:
            print(f"Piece {piece_index} failed hash check")
            return

    # Save to file
    with open(output_file, "wb") as f:
        f.write(pieces_data)
    print(f"Downloaded {decoded_data['info']['name']} to {output_file}")


def download_piece(decoded_data, info_hash, piece_index):
    peers = get_peers(decoded_data, info_hash)
    if not peers:
        print("No peers found")
        return None

    peer_ip, peer_port = peers[0].split(":")
    peer_port = int(peer_port)

    protocol_name_length = struct.pack(">B", 19)
    protocol_name = b"BitTorrent protocol"
    reserved_bytes = b"\x00" * 8
    peer_id = b"00112233445566778899"  # Consider generating a unique peer ID
    handshake = (
        protocol_name_length + protocol_name + reserved_bytes + info_hash + peer_id
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((peer_ip, peer_port))
        sock.send(handshake)
        response = sock.recv(68)
        print(f"Peer ID: {response[48:].hex()}")

        while True:
            message = receive_message(sock)
            if int.from_bytes(message[4:5], byteorder='big') == 5:
                break

        interested_payload = struct.pack(">IB", 1, 2)
        sock.sendall(interested_payload)
        message = receive_message(sock)
        if int.from_bytes(message[4:5], byteorder='big') != 1:
            raise RuntimeError("Failed to receive 'unchoke' message")

        file_length = decoded_data["info"].get("length", 0)
        piece_length = decoded_data["info"].get("piece length", 0)
        if piece_index == (len(decoded_data["info"]["pieces"]) // 20) - 1:
            piece_length = file_length - (piece_length * piece_index)

        number_of_blocks = math.ceil(piece_length / (16 * 1024))
        data = bytearray()
        for block_index in range(number_of_blocks):
            begin = 2**14 * block_index
            block_length = min(piece_length - begin, 2**14)
            request_payload = struct.pack(">IBIII", 13, 6, piece_index, begin, block_length)
            sock.sendall(request_payload)
            message = receive_message(sock)
            data.extend(message[13:])

        return data

    except Exception as e:
        print(f"An error occurred while downloading piece {piece_index}: {e}")
        return None

    finally:
        sock.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: <command> [args...]")
        return

    command = sys.argv[1]

    if command == "decode":
        if len(sys.argv) < 3:
            print("Usage: decode <bencoded_string>")
            return
        bencoded_value = sys.argv[2].encode()
        decoded_value = decode_bencode(bencoded_value)
        print(json.dumps(decoded_value, default=bytes_to_str, separators=(',', ':')))

    elif command == "info":
        if len(sys.argv) < 3:
            print("Usage: info <torrent_file>")
            return
        file_name = sys.argv[2]
        with open(file_name, "rb") as torrent_file:
            bencoded_content = torrent_file.read()
        torrent = decode_bencode(bencoded_content)
        info_hash = hashlib.sha1(bencodepy.encode(torrent["info"])).digest()
        print("Tracker URL:", bytes_to_str(torrent["announce"]))
        print("Length:", torrent["info"]["length"])
        print(f"Info Hash: {info_hash.hex()}")
        print("Piece Length:", torrent["info"]["piece length"])
        for i in range(0, len(torrent["info"]["pieces"]), 20):
            print(torrent["info"]["pieces"][i: i + 20].hex())

    elif command == "peers":
        if len(sys.argv) < 3:
            print("Usage: peers <torrent_file>")
            return
        file_name = sys.argv[2]
        with open(file_name, "rb") as f:
            bencoded_value = f.read()
        torrent_info = decode_bencode(bencoded_value)
        tracker_url = bytes_to_str(torrent_info.get("announce", b""))
        info_dict = torrent_info.get("info", {})
        bencoded_info = bencodepy.encode(info_dict)
        info_hash = hashlib.sha1(bencoded_info).digest()
        params = {
            "info_hash": info_hash,
            "peer_id": "00112233445566778899",
            "port": 6881,
            "uploaded": 0,
            "downloaded": 0,
            "left": info_dict.get("length", 0),
            "compact": 1,
        }
        response = requests.get(tracker_url, params=params)
        response_dict = decode_bencode(response.content)
        peers = response_dict.get("peers", b"")
        for i in range(0, len(peers), 6):
            ip = ".".join(str(b) for b in peers[i: i + 4])
            port = struct.unpack("!H", peers[i + 4: i + 6])[0]
            print(f"Peer: {ip}:{port}")

    elif command == "handshake":
        if len(sys.argv) < 4:
            print("Usage: handshake <torrent_file> <peer_ip:peer_port>")
            return
        file_name = sys.argv[2]
        ip, port = sys.argv[3].split(":")
        port = int(port)
        with open(file_name, "rb") as f:
            bencoded_value = f.read()
        torrent_info = decode_bencode(bencoded_value)
        info_hash = hashlib.sha1(bencodepy.encode(torrent_info["info"])).digest()

        protocol_name_length = struct.pack(">B", 19)
        protocol_name = b"BitTorrent protocol"
        reserved_bytes = b"\x00" * 8
        peer_id = b"00112233445566778899"
        handshake = (
            protocol_name_length + protocol_name + reserved_bytes + info_hash + peer_id
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((ip, port))
            sock.send(handshake)
            response = sock.recv(68)
            print(f"Peer ID: {response[48:].hex()}")
        finally:
            sock.close()

    elif command == "download":
        if "-o" in sys.argv:
            output_index = sys.argv.index("-o") + 1
            if output_index >= len(sys.argv):
                print("Usage: download -o <output_file> <torrent_file>")
                return
            output_file = sys.argv[output_index]
            torrent_file = sys.argv[output_index + 1]
        else:
            print("Usage: download -o <output_file> <torrent_file>")
            return

        with open(torrent_file, "rb") as f:
            bencoded_value = f.read()
        torrent_info = decode_bencode(bencoded_value)
        info_hash = hashlib.sha1(bencodepy.encode(torrent_info["info"])).digest()
        download_file(torrent_info, info_hash, output_file)
        print(f"Downloaded {torrent_file} to {output_file}")

    elif command == "download_piece":
        if "-o" in sys.argv:
            output_index = sys.argv.index("-o") + 1
            if output_index >= len(sys.argv):
                print("Usage: download_piece -o <output_file> <torrent_file> <piece_index>")
                return
            output_file = sys.argv[output_index]
            torrent_file = sys.argv[output_index + 1]
            piece_index = int(sys.argv[output_index + 2])
        else:
            print("Usage: download_piece -o <output_file> <torrent_file> <piece_index>")
            return

        with open(torrent_file, "rb") as f:
            bencoded_value = f.read()
        torrent_info = decode_bencode(bencoded_value)
        info_hash = hashlib.sha1(bencodepy.encode(torrent_info["info"])).digest()
        piece_data = download_piece(torrent_info, info_hash, piece_index)
        if piece_data:
            with open(output_file, "wb") as f:
                f.write(piece_data)
            print(f"Downloaded piece {piece_index} to {output_file}")

    else:
        print("Unknown command. Usage: decode | info | peers | handshake | download | download_piece")


if __name__=="__main__":
    main()