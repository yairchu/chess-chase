# UI screenshots

Generated comparison screenshots go here.

Run:

```sh
bash tools/capture-ui-screenshots.sh
```

The script writes desktop captures and iPhone 17 portrait captures. On Retina Macs, Kivy exports screenshots at device-pixel scale, so the script requests `603x1311` logical points to produce `1206x2622` PNGs.
