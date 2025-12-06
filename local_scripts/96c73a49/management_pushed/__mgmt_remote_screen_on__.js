if ((typeof isScreenOn === "function" && !isScreenOn()) || (!this.isScreenOn && device.isScreenOff && device.isScreenOff())) {
  if (device.wakeUp) { device.wakeUp(); }
}
