https://www.dropbox.com/developers/documentation/python#tutorial
https://stackoverflow.com/questions/70641660/how-do-you-get-and-use-a-refresh-token-for-the-dropbox-api-python-3-x

# 1. register dropbox application
https://www.dropbox.com/developers/apps

# 2. get token
https://www.dropbox.com/oauth2/authorize?client_id=<APP_KEY>&token_access_type=offline&response_type=code

Complete the code flow on the Authorization URL. You will receive an AUTHORIZATION_CODE at the end.

# 3. get the permanent refres token:
curl --location 'https://api.dropboxapi.com/oauth2/token' \
--header 'Content-Type: application/x-www-form-urlencoded' \
--header 'Authorization: Basic <APP_KEY>:<APP_SECRET>' \
--data-urlencode 'code=<AUTH CODE>' \
--data-urlencode 'grant_type=authorization_code'



```bash

# post file

curl -X POST https://content.dropboxapi.com/2/files/upload \
  --header 'Authorization: Bearer <token>' \
  --header 'Content-Type: application/octet-stream' \
  --header 'Dropbox-API-Arg: {"path":"Espacio familiar\\recibos compras","mode":{".tag":"add"},"autorename":true}' \
  --data-binary @'img-DXnLbR6bzVe2QEssbat62iye.png'


#coger carpetas de espacio familiar
curl -X POST https://api.dropboxapi.com/2/files/list_folder \
  --header 'Authorization: Bearer <token>' \
  --header 'Content-Type: application/json' \
  --data '{"path":"id:I9qyFus3r3cAAAAAAAxXUg"}'



#billetes
id:fLIJ4o8p0TAAAAAAAAAAHw

#intercambio
id:fLIJ4o8p0TAAAAAAAAAAPw


#recibos compras
id:fLIJ4o8p0TAAAAAAAAAACw


```

