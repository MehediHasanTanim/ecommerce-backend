import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_login(api_client, create_user):
    user = create_user(email="login@example.com")
    url = reverse('token_obtain_pair')
    response = api_client.post(url, {
        'email': 'login@example.com',
        'password': 'testpass123'
    })
    
    assert response.status_code == 200
    assert 'access' in response.data
    assert 'refresh' in response.data
