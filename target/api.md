# Booking API documentation

Base URL: http://localhost:3001 (see your run instructions for the actual port)

This is the public documentation of the API under test, converted from its apidoc page.

## CreateToken: POST /auth

Creates a new auth token to use for access to the PUT and DELETE /booking

**Request example: Example 1:**

```
curl -X POST \
  http://localhost:3001/auth \
  -H 'Content-Type: application/json' \
  -d '{
    "username" : "admin",
    "password" : "password123"
}'
```

**Headers: Header**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| Content-Type | string | no | Sets the format of payload you are sending |


**Request: Request body**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| username | String | no | Username for authentication |
| password | String | no | Password for authentication |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| token | String | no | Token to use in future requests |

**Response example: Response:**

```
HTTP/1.1 200 OK

{
    "token": "abc123"
}
```

## GetBooking: GET /booking/:id

Returns a specific booking based upon the booking id provided

**Request example: Example 1 (Get booking):**

```
curl -i http://localhost:3001/booking/1
```

**Headers: Header**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| Accept | string | no | Sets what format the response body is returned in. Can be application/json or application/xml |


**Request: Url Parameter**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| id | String | no | The id of the booking you would like to retrieve |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | no | Firstname for the guest who made the booking |
| lastname | String | no | Lastname for the guest who made the booking |
| totalprice | Number | no | The total price for the booking |
| depositpaid | Boolean | no | Whether the deposit has been paid or not |
| bookingdates | Object | no | Sub-object that contains the checkin and checkout dates |
| bookingdates.checkin | Date | no | Date the guest is checking in |
| bookingdates.checkout | Date | no | Date the guest is checking out |
| additionalneeds | String | no | Any other needs the guest has |

**Response example: JSON Response:**

```
HTTP/1.1 200 OK

{
    "firstname": "Sally",
    "lastname": "Brown",
    "totalprice": 111,
    "depositpaid": true,
    "bookingdates": {
        "checkin": "2013-02-23",
        "checkout": "2014-10-23"
    },
    "additionalneeds": "Breakfast"
}
```

**Response example: XML Response:**

```
HTTP/1.1 200 OK

<booking>
    <firstname>Sally</firstname>
    <lastname>Brown</lastname>
    <totalprice>111</totalprice>
    <depositpaid>true</depositpaid>
    <bookingdates>
        <checkin>2013-02-23</checkin>
        <checkout>2014-10-23</checkout>
    </bookingdates>
    <additionalneeds>Breakfast</additionalneeds>
</booking>
```

**Response example: URL Response:**

```
HTTP/1.1 200 OK

firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2019-01-01
```

## CreateBooking: POST /booking

Creates a new booking in the API

**Request example: JSON example usage:**

```
curl -X POST \
  http://localhost:3001/booking \
  -H 'Content-Type: application/json' \
  -d '{
    "firstname" : "Jim",
    "lastname" : "Brown",
    "totalprice" : 111,
    "depositpaid" : true,
    "bookingdates" : {
        "checkin" : "2018-01-01",
        "checkout" : "2019-01-01"
    },
    "additionalneeds" : "Breakfast"
}'
```

**Request example: XML example usage:**

```
curl -X POST \
  http://localhost:3001/booking \
  -H 'Content-Type: text/xml' \
  -d '<booking>
    <firstname>Jim</firstname>
    <lastname>Brown</lastname>
    <totalprice>111</totalprice>
    <depositpaid>true</depositpaid>
    <bookingdates>
      <checkin>2018-01-01</checkin>
      <checkout>2019-01-01</checkout>
    </bookingdates>
    <additionalneeds>Breakfast</additionalneeds>
  </booking>'
```

**Request example: URLencoded example usage:**

```
curl -X POST \
  http://localhost:3001/booking \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'
```

**Headers: Header**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| Content-Type | string | no | Sets the format of payload you are sending. Can be application/json or text/xml |
| Accept | string | no | Sets what format the response body is returned in. Can be application/json or application/xml |


**Request: Request body**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | no | Firstname for the guest who made the booking |
| lastname | String | no | Lastname for the guest who made the booking |
| totalprice | Number | no | The total price for the booking |
| depositpaid | Boolean | no | Whether the deposit has been paid or not |
| bookingdates.checkin | Date | no | Date the guest is checking in |
| bookingdates.checkout | Date | no | Date the guest is checking out |
| additionalneeds | String | no | Any other needs the guest has |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| bookingid | Number | no | ID for newly created booking |
| booking | Object | no | Object that contains |
| booking.firstname | String | no | Firstname for the guest who made the booking |
| booking.lastname | String | no | Lastname for the guest who made the booking |
| booking.totalprice | Number | no | The total price for the booking |
| booking.depositpaid | Boolean | no | Whether the deposit has been paid or not |
| booking.bookingdates | Object | no | Sub-object that contains the checkin and checkout dates |
| booking.bookingdates.checkin | Date | no | Date the guest is checking in |
| booking.bookingdates.checkout | Date | no | Date the guest is checking out |
| booking.additionalneeds | String | no | Any other needs the guest has |

**Response example: JSON Response:**

```
HTTP/1.1 200 OK

{
    "bookingid": 1,
    "booking": {
        "firstname": "Jim",
        "lastname": "Brown",
        "totalprice": 111,
        "depositpaid": true,
        "bookingdates": {
            "checkin": "2018-01-01",
            "checkout": "2019-01-01"
        },
        "additionalneeds": "Breakfast"
    }
}
```

**Response example: XML Response:**

```
HTTP/1.1 200 OK

<?xml version='1.0'?>
<created-booking>
    <bookingid>1</bookingid>
    <booking>
        <firstname>Jim</firstname>
        <lastname>Brown</lastname>
        <totalprice>111</totalprice>
        <depositpaid>true</depositpaid>
        <bookingdates>
            <checkin>2018-01-01</checkin>
            <checkout>2019-01-01</checkout>
        </bookingdates>
        <additionalneeds>Breakfast</additionalneeds>
    </booking>
</created-booking>
```

**Response example: URL Response:**

```
HTTP/1.1 200 OK

bookingid=1&booking%5Bfirstname%5D=Jim&booking%5Blastname%5D=Brown&booking%5Btotalprice%5D=111&booking%5Bdepositpaid%5D=true&booking%5Bbookingdates%5D%5Bcheckin%5D=2018-01-01&booking%5Bbookingdates%5D%5Bcheckout%5D=2019-01-01
```

## UpdateBooking: PUT /booking/:id

Updates a current booking

**Request example: JSON example usage:**

```
curl -X PUT \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'Cookie: token=abc123' \
  -d '{
    "firstname" : "James",
    "lastname" : "Brown",
    "totalprice" : 111,
    "depositpaid" : true,
    "bookingdates" : {
        "checkin" : "2018-01-01",
        "checkout" : "2019-01-01"
    },
    "additionalneeds" : "Breakfast"
}'
```

**Request example: XML example usage:**

```
curl -X PUT \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: text/xml' \
  -H 'Accept: application/xml' \
  -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' \
  -d '<booking>
    <firstname>James</firstname>
    <lastname>Brown</lastname>
    <totalprice>111</totalprice>
    <depositpaid>true</depositpaid>
    <bookingdates>
      <checkin>2018-01-01</checkin>
      <checkout>2019-01-01</checkout>
    </bookingdates>
    <additionalneeds>Breakfast</additionalneeds>
  </booking>'
```

**Request example: URLencoded example usage:**

```
curl -X PUT \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Accept: application/x-www-form-urlencoded' \
  -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' \
  -d 'firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'
```

**Headers: Header**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| Content-Type | string | no | Sets the format of payload you are sending. Can be application/json or text/xml |
| Accept | string | no | Sets what format the response body is returned in. Can be application/json or application/xml |
| Cookie | string | yes | Sets an authorization token to access the PUT endpoint, can be used as an alternative to the Authorization |
| Authorization | string | yes | YWRtaW46cGFzc3dvcmQxMjM=]   Basic authorization header to access the PUT endpoint, can be used as an alternative to the Cookie header |


**Request: Url Parameter**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| id | Number | no | ID for the booking you want to update |

**Request: Request body**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | no | Firstname for the guest who made the booking |
| lastname | String | no | Lastname for the guest who made the booking |
| totalprice | Number | no | The total price for the booking |
| depositpaid | Boolean | no | Whether the deposit has been paid or not |
| bookingdates.checkin | Date | no | Date the guest is checking in |
| bookingdates.checkout | Date | no | Date the guest is checking out |
| additionalneeds | String | no | Any other needs the guest has |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | no | Firstname for the guest who made the booking |
| lastname | String | no | Lastname for the guest who made the booking |
| totalprice | Number | no | The total price for the booking |
| depositpaid | Boolean | no | Whether the deposit has been paid or not |
| bookingdates | Object | no | Sub-object that contains the checkin and checkout dates |
| bookingdates.checkin | Date | no | Date the guest is checking in |
| bookingdates.checkout | Date | no | Date the guest is checking out |
| additionalneeds | String | no | Any other needs the guest has |

**Response example: JSON Response:**

```
HTTP/1.1 200 OK

{
    "firstname" : "James",
    "lastname" : "Brown",
    "totalprice" : 111,
    "depositpaid" : true,
    "bookingdates" : {
        "checkin" : "2018-01-01",
        "checkout" : "2019-01-01"
    },
    "additionalneeds" : "Breakfast"
}
```

**Response example: XML Response:**

```
HTTP/1.1 200 OK

<booking>
    <firstname>James</firstname>
    <lastname>Brown</lastname>
    <totalprice>111</totalprice>
    <depositpaid>true</depositpaid>
    <bookingdates>
      <checkin>2018-01-01</checkin>
      <checkout>2019-01-01</checkout>
    </bookingdates>
    <additionalneeds>Breakfast</additionalneeds>
</booking>
```

**Response example: URL Response:**

```
HTTP/1.1 200 OK

firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2019-01-01
```

## PartialUpdateBooking: PATCH /booking/:id

Updates a current booking with a partial payload

**Request example: JSON example usage:**

```
curl -X PUT \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'Cookie: token=abc123' \
  -d '{
    "firstname" : "James",
    "lastname" : "Brown"
}'
```

**Request example: XML example usage:**

```
curl -X PUT \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: text/xml' \
  -H 'Accept: application/xml' \
  -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' \
  -d '<booking>
    <firstname>James</firstname>
    <lastname>Brown</lastname>
  </booking>'
```

**Request example: URLencoded example usage:**

```
curl -X PUT \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -H 'Accept: application/x-www-form-urlencoded' \
  -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' \
  -d 'firstname=Jim&lastname=Brown'
```

**Headers: Header**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| Content-Type | string | no | Sets the format of payload you are sending. Can be application/json or text/xml |
| Accept | string | no | Sets what format the response body is returned in. Can be application/json or application/xml |
| Cookie | string | yes | Sets an authorization token to access the PUT endpoint, can be used as an alternative to the Authorization |
| Authorization | string | yes | YWRtaW46cGFzc3dvcmQxMjM=]   Basic authorization header to access the PUT endpoint, can be used as an alternative to the Cookie header |


**Request: Url Parameter**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| id | Number | no | ID for the booking you want to update |

**Request: Request body**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | yes | Firstname for the guest who made the booking |
| lastname | String | yes | Lastname for the guest who made the booking |
| totalprice | Number | yes | The total price for the booking |
| depositpaid | Boolean | yes | Whether the deposit has been paid or not |
| bookingdates.checkin | Date | yes | Date the guest is checking in |
| bookingdates.checkout | Date | yes | Date the guest is checking out |
| additionalneeds | String | yes | Any other needs the guest has |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | no | Firstname for the guest who made the booking |
| lastname | String | no | Lastname for the guest who made the booking |
| totalprice | Number | no | The total price for the booking |
| depositpaid | Boolean | no | Whether the deposit has been paid or not |
| bookingdates | Object | no | Sub-object that contains the checkin and checkout dates |
| bookingdates.checkin | Date | no | Date the guest is checking in |
| bookingdates.checkout | Date | no | Date the guest is checking out |
| additionalneeds | String | no | Any other needs the guest has |

**Response example: JSON Response:**

```
HTTP/1.1 200 OK

{
    "firstname" : "James",
    "lastname" : "Brown",
    "totalprice" : 111,
    "depositpaid" : true,
    "bookingdates" : {
        "checkin" : "2018-01-01",
        "checkout" : "2019-01-01"
    },
    "additionalneeds" : "Breakfast"
}
```

**Response example: XML Response:**

```
HTTP/1.1 200 OK

<booking>
    <firstname>James</firstname>
    <lastname>Brown</lastname>
    <totalprice>111</totalprice>
    <depositpaid>true</depositpaid>
    <bookingdates>
      <checkin>2018-01-01</checkin>
      <checkout>2019-01-01</checkout>
    </bookingdates>
    <additionalneeds>Breakfast</additionalneeds>
</booking>
```

**Response example: URL Response:**

```
HTTP/1.1 200 OK

firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2019-01-01
```

## DeleteBooking: DELETE /booking/1

Deletes a booking from the API. Requires an authorization token to be set in the header or a Basic auth header.

**Request example: Example 1 (Cookie):**

```
curl -X DELETE \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: application/json' \
  -H 'Cookie: token=abc123'
```

**Request example: Example 2 (Basic auth):**

```
curl -X DELETE \
  http://localhost:3001/booking/1 \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='
```

**Headers: Header**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| Cookie | string | yes | Sets an authorization token to access the DELETE endpoint, can be used as an alternative to the Authorization |
| Authorization | string | yes | YWRtaW46cGFzc3dvcmQxMjM=]   Basic authorization header to access the DELETE endpoint, can be used as an alternative to the Cookie header |


**Request: Url Parameter**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| id | Number | no | ID for the booking you want to update |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| OK | String | no | Default HTTP 201 response |

**Response example: Response:**

```
HTTP/1.1 201 Created
```

## GetBookingIds: GET /booking

Returns the ids of all the bookings that exist within the API. Can take optional query strings to search and return a subset of booking ids.

**Request example: Example 1 (All IDs):**

```
curl -i http://localhost:3001/booking
```

**Request example: Example 2 (Filter by name):**

```
curl -i http://localhost:3001/booking?firstname=sally&lastname=brown
```

**Request example: Example 3 (Filter by checkin/checkout date):**

```
curl -i http://localhost:3001/booking?checkin=2014-03-13&checkout=2014-05-21
```


**Request: Parameter**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| firstname | String | yes | Return bookings with a specific firstname |
| lastname | String | yes | Return bookings with a specific lastname |
| checkin | date | yes | Return bookings that have a checkin date greater than or equal to the set checkin date. Format must be CCYY-MM-DD |
| checkout | date | yes | Return bookings that have a checkout date greater than or equal to the set checkout date. Format must be CCYY-MM-DD |


**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| object | object[] | no | Array of objects that contain unique booking IDs |
| object.bookingid | number | no | ID of a specific booking that matches search criteria |

**Response example: Response:**

```
HTTP/1.1 200 OK

[
  {
    "bookingid": 1
  },
  {
    "bookingid": 2
  },
  {
    "bookingid": 3
  },
  {
    "bookingid": 4
  }
]
```

## HealthCheck: GET /ping

A simple health check endpoint to confirm whether the API is up and running.

**Request example: Ping server:**

```
curl -i http://localhost:3001/ping
```



**Response: Success 200**

| Field | Type | Optional | Description |
| --- | --- | --- | --- |
| OK | String | no | Default HTTP 201 response |

**Response example: Response:**

```
HTTP/1.1 201 Created
```

