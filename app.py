from classes.ApplicationController import ApplicationController

if __name__ == '__main__':
    app = ApplicationController()
    app.setup()

    app.run(host='0.0.0.0', port=4986, debug=True)
