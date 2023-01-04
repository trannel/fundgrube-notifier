# Fundgrube Notifier

This project notifies you about current offers from the German electronics retail chains Saturn and Media Markt in their Fundgrube, that match specific conditions you can define.

## Setup

Before you start make sure [python 3.9](https://www.python.org/downloads/) (or higher) and [poetry](https://python-poetry.org/docs/) are installed on your machine.

First, clone the project, navigate to its root directory, and install the dependencies (this automatically creates a virtual environment):
```bash
poetry install
```

Next, rename the file `sample_products.json` in the `data` directory to `products.json` and fill it as specified in the [Options](#options) section.

### Email notifications

If you want to get email notifications, the easiest way is to use a [Google account](https://www.google.com/account/about/) (for Gmail)
with [2FA](https://support.google.com/accounts/answer/185839) enabled.
In your account you have to generate an [app password](https://support.google.com/accounts/answer/185833) for Gmail.
While creating the password select "Mail" as app and "Other" as device (select as custom name you see fit, e.g., " Raspberry Pi").
We need to use app passwords (which in turn require 2FA) due to a [policy change](https://support.google.com/accounts/answer/6010255) in mid-2022.
Lastly, you have to rename the `sample.env` to `.env` and fill it as follows:
- `MAIL_SENDER` The gmail address you want to send the emails from.
- `MAIL_PASSWORD` The 16-digit app password you generated.
- `MAIL_RECEIVER` If you want to receive the emails on another address, set it here. (Optional)

If you do not want to use Gmail you also have to specify:
- `SMTP_SERVER` The SMTP server of your email provider.
- `SMTP_PORT` The corresponding SMTP port.

Be aware though, that non-Gmail approaches might run into issues with 2FA etc. and were not tested.

## Usage

Once everything is set up, you can run the script with
```bash
poetry run python fundgrube_notifier.py
```

### Cron job

You can also set up a cron job (or something similar) to automatically execute the script every hour.
For this, open the cron tab with
```bash
crontab -e
```
and then add the following line to configure the cron job (replace `<path>` with the path to this project's root directory):
```crontab
10 8-23 * * * cd <path>/fundgrube-notifier && poetry run python fundgrube_notifier.py
```
Make sure that cron has access to the correct `$PATH` (e.g., for poetry), by copying the following line *above* the definition of the cron job (replace `<user>` with your device's username):
```bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin:/home/<user>/.local/bin
```
See [this](https://stackoverflow.com/questions/2388087/how-to-get-cron-to-call-in-the-correct-paths) Stack Overflow post for more details regarding cron and `$PATH`.

### Options

Entries in the `products.json` file are created in JSON format and every JSON object can have the following attributes to filter the available articles:
- **include**: A list of terms that must appear in the name of the article (case-insensitive). Mandatory attribute.
- **price**: Articles with a higher price are ignored. Optional attribute.
- **exclude**: A list of terms, that must *not* appear in the name of the article (case-insensitive). Optional attribute.

When choosing the terms for `include` and `exclude`, remember that only simple string matching is done, so sometimes only using substrings might be beneficial.

### Example

https://github.com/trannel/fundgrube-notifier/blob/14e2a8eee97d0efdf3dd9cb79cb869f48606f61a/sample_products.json#L1-L10

## Fundgrube

The Fundgrube has special offers that are usually very limited in numbers and can be found here:
- Saturn: https://www.saturn.de/de/data/fundgrube
- Media Markt: https://www.mediamarkt.de/de/data/fundgrube

### Data

This project is using already preprocessed data, which is crawled hourly by a script
from [Barney](https://www.mydealz.de/profile/Barney) at [mydealz](https://www.mydealz.de/):

- Saturn: https://schneinet.de/saturn.html
- Media Markt: https://schneinet.de/mediamarkt.html

More info:
https://www.mydealz.de/diskussion/die-saturn-fundgrube-ist-da-einzelstucke-in-einzelnen-markten-gunstig-kaufen-1764598
 
