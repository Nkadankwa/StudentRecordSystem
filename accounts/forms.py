from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Unable to sign in. Check your username and password.',
        'inactive': 'Unable to sign in. Check your username and password.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(autocomplete='username', autofocus=True)
        self.fields['password'].widget.attrs.update(autocomplete='current-password')

    def full_clean(self):
        super().full_clean()
        for name in self.fields:
            if name in self.errors:
                self.fields[name].widget.attrs.update({
                    'aria-invalid': 'true',
                    'aria-describedby': f'id_{name}_errors',
                })
