from database import connect


class UserService:
    def get_user(self, user_id):
        return connect(user_id)
