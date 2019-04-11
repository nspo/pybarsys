# API
Pybarsys provides a simple REST API. All endpoints use `application/json` as Content-Type.
Currently available are:
* GET:
  * User
  * Product
  * Purchase
* POST:
  * Purchase

URL: `<host>:<port>/api/<endpoint>`
  So lets say your host domain is `example.com` and pybarsys is running on port `3000`. A request to get a JSON containing all users would be:
```bash
curl example.com:3000/api/user/
```
A request for creating a new purchase could look like this:

```bash
curl -X POST -H "Content-Type: application/json" --data @purchase.json example.com:3000/api/purchase/
```
With a JSON (saved as `purchase.json`) looking like this:
```json
{
  "user_id":3,
  "quantity":1,
  "product_id":"2",
  "comment":"I am an API purchase",
  "give_away_free":true
}
```
in which `comment` and `give_away_free` are optional and will default to `""` and `false` respectively.
