from services import UserService


def main():
    service = UserService()
    return service.get_user(42)
