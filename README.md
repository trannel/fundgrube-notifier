# Fundgrube notifier

This project notifies you about current offers from the German electronics retail chains Saturn and Media Markt in their
Fundgrube, that match specific conditions you can define.

## Setup

Before you start make sure python 3 is installed on your machine.
First, clone the project and install the required packages with
```sh
pip install -r requirements.txt
```

Next, rename the file `sample_products.json` in the root directory of the project to `products.json` and fill it as specified in the [Options](#options) section.

If you want to get email notifications, the easiest way is to use a [Google account](https://www.google.com/account/about/) (for Gmail)
with [2FA](https://support.google.com/accounts/answer/185839) enabled.
In your account you have to generate an [app password](https://support.google.com/accounts/answer/185833) for Gmail.
While creating the password select "Mail" as app and "Other" as device (select as custom name you see fit, e.g., " Raspberry Pi").
We need to use app passwords (which in turn require 2FA) due to a [policy change](https://support.google.com/accounts/answer/6010255) in mid-2022.
Lastly, you have to rename the `sample.env` to `.env` and fill it as follows:
- `MAIL_SENDER` The gmail address you want to send the emails from.
- `MAIL_PWD` The 16-digit app password you generated.
- `MAIL_RECEIVER` If you want to receive the emails on another address, set it here. (Optional)

If you do not want to use Gmail you also have to specify:
- `MAIL_SERVER` The SMTP server of your email provider.
- `MAIL_PORT` The SMTP port.

Be aware though, that non-Gmail approaches might run into issues with 2FA etc.

## Usage

Once everything is set up, you can run the `main.py` with
```sh
python main.py
```

You can also set up a cron job (or something similar) to automatically execute the script every hour.

### Options

Entries in the `products.json` file are created in JSON format and every JSON object can have the following attributes
to filter the
available articles:
- **include**: A list of terms that must appear in the name of the article (case-insensitive). Mandatory attribute.
- **price**: Articles with a higher price are ignored. Optional attribute.
- **exclude**: A list of terms, that must *not* appear in the name of the article (case-insensitive). Optional
  attribute.

When choosing the terms for `include` and `exclude`, remember that we only do simple string matching, so sometimes only using substrings might be beneficial.

### Example

See [sample_products.json](sample_products.json):

```json
[
  {
    "include": ["sony", "tv"],
    "exclude": ["lcd"]
  },
  {
    "include": ["playstation"],
    "price": 20
  }
]
```

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
 