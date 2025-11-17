import queue

from flask import Flask, render_template, Response


class AudioHttpFacade:
    def __init__(self, audioStreamer):
        self.app = Flask(__name__)
        self.audioStreamer = audioStreamer
        self._add_routes()

    def run(self, host: str, port: int, debug: bool):
        print(f"Server listening on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug, threaded=True)

    # -- PRIVATES --

    def _add_routes(self):
        self.app.add_url_rule('/', 'player', self._player)
        self.app.add_url_rule('/stream', 'stream', self._stream)
        self.app.add_url_rule('/stats', 'stats', self._stats)

    def _generateAudioStream(self):
        clientQueue = queue.Queue(maxsize=100)
        self.audioStreamer.addClient(clientQueue)

        try:
            while True:
                data = clientQueue.get()
                yield data
        except GeneratorExit:
            self.audioStreamer.removeClient(clientQueue)

    # Routes

    def _player(self):
        return render_template('index.html')

    def _stream(self):
        return Response(
            self._generateAudioStream(),
            mimetype='audio/x-wav'
        )

    def _stats(self):
        return self.audioStreamer.getStats()
