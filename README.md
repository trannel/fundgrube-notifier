# Fundgrube notifier

This project notifies you about current offers from the German electronics retail chains Saturn and Media Markt in their
Fundgrube, that match specific conditions you can define.

## Usage

First, install the project and the required packages from the `requirements.txt`.
Next, create a file called `products.json` in the root directory of the project, and once it is filled, run
the `main.py`.
Entries in the file are created in JSON format and every JSON object can have the following attributes:

- terms: A list of terms that must be included in the name of the article (case-insensitive). Mandatory attribute.
- price: You will not get a notification, if this price is surpassed. Optional attribute.

Example:

```json
[
  {
    "terms": ["sony", "tv"]
  },
  {
    "terms": ["playstation"],
    "price": 20
  }
]
```

You will get notification for every article with the terms "sony" and "tv" in the name regardless of its price and every
product with "playstation" that is 20€ or less.

## Fundgrube

The Fundgrube has special offers that are usually very limited in numbers and can be found here

- Saturn: https://www.saturn.de/de/data/fundgrube
- Media Markt: https://www.mediamarkt.de/de/data/fundgrube

### Data

The project is using already preprocessed data, which is crawled hourly by a script
from [Barney](https://www.mydealz.de/profile/Barney) at [mydealz](https://www.mydealz.de/):

- Saturn: https://schneinet.de/saturn.html
- Media Markt: https://schneinet.de/mediamarkt.html

More info:
https://www.mydealz.de/diskussion/die-saturn-fundgrube-ist-da-einzelstucke-in-einzelnen-markten-gunstig-kaufen-1764598
 