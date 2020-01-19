class RegistrationError(Exception):
    def __init__(self, code):
        self.code = code

    def get_code(self):
        return str(code)

class DeregistrationError(Exception):
    def __init__(self, code):
        self.code = code

    def get_code(self):
        return str(code)

class DatabaseError(Exception):
    def __init__(self, code):
        self.code = code

    def get_code(self):
        return str(code)

