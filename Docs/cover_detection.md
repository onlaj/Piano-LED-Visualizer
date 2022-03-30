Implementing a keyboard cover detection depends highly on your specific model. Basically any type of switch will work,
that closes the circuit when the cover is closed. For example, you can use a mechanical switch that is placed
underneath the cover and will be closed by the cover. Alternatively you can use a magnetic reed switch (will be used as
example). 

Wire one end of the switch to GPIO PIN 12 on your pi. The other end must be connected to ground. You can share the
ground line used by the RGB strip.

![coverdetection_pic](../Docs/pics/coverdetection_pic.jpg)

In this example the reed switch is taped down onto the piano. A small neodymium magnet is mounted behind the cover and
sits directly in front of the reed switch when being closed. One wire goes to the raspberry GPIO PIN 12, the other
shares the ground supply of the RGB strip.
