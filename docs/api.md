# API
The system provides a simple API. All Endpoints use `application/json` as Content-Type.
Currently available are:
* GET:
  * User
  * Product
  * Purchase
* POST:
  * Purchase

URL: `<yourRootUrl>:<port>/api/<endpoint>`
  So lets say your URL is `www.myFancyUrl.com` and the application is running on port `3000`. A request to get a JSON containing all users would be:
```bash
curl www.myFancyUrl.com:3000/api/user/
```
The request for creating a new purchase would look like this:

```bash
curl -X POST -H "Content-Type: application/json" --data @purchase.json www.myFancyUrl.com:3000/api/purchase/
```
With a JSON looking like this:
```
{
  "user_id":3,
  "quantity":1,
  "product_id":"2",
  "comment":"I am an API purchase",
  "give_away_free":true
}
```
in which `comment` and `give_away_free` are optional and will default to `""` and `false` respectively.