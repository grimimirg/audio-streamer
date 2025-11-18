from classes.ApplicationController import ApplicationController
from utils.Constants import HOST_ADDR, PORT, DEBUG

if __name__ == '__main__':
    app = ApplicationController()
    app.setup()

    app.run(host=HOST_ADDR, port=PORT, debug=DEBUG)
