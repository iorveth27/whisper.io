#!/usr/bin/env python3
"""Floating overlay indicator for Whisper Dictate — native macOS using AppKit."""

import os
import sys
import threading

import AppKit
import objc
from Foundation import NSTimer, NSRunLoop, NSDefaultRunLoopMode


class OverlayWindow:
    """A small floating window that shows a red pulsing dot + 'Listening...' at top-center."""

    def __init__(self):
        self.app = AppKit.NSApplication.sharedApplication()
        self.app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        # Window size and position (top-center)
        screen = AppKit.NSScreen.mainScreen().frame()
        win_w, win_h = 200, 40
        x = (screen.size.width - win_w) / 2
        y = screen.size.height - win_h - 10  # macOS coords: bottom-left origin

        style = AppKit.NSWindowStyleMaskBorderless
        window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (win_w, win_h)),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        window.setLevel_(AppKit.NSFloatingWindowLevel + 1)
        window.setOpaque_(False)
        window.setAlphaValue_(0.9)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.setHasShadow_(True)
        window.setIgnoresMouseEvents_(True)
        window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
        )

        # Content view with rounded background
        content = AppKit.NSView.alloc().initWithFrame_(((0, 0), (win_w, win_h)))
        window.setContentView_(content)

        # Dark rounded background
        bg = RoundedView.alloc().initWithFrame_(((0, 0), (win_w, win_h)))
        content.addSubview_(bg)

        # Red dot
        self.dot = AppKit.NSTextField.alloc().initWithFrame_(((12, 6), (28, 28)))
        self.dot.setStringValue_("\u25cf")
        self.dot.setFont_(AppKit.NSFont.systemFontOfSize_(22))
        self.dot.setTextColor_(AppKit.NSColor.redColor())
        self.dot.setBezeled_(False)
        self.dot.setDrawsBackground_(False)
        self.dot.setEditable_(False)
        self.dot.setSelectable_(False)
        content.addSubview_(self.dot)

        # Label
        label = AppKit.NSTextField.alloc().initWithFrame_(((40, 8), (150, 24)))
        label.setStringValue_("Listening...")
        label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(15))
        label.setTextColor_(AppKit.NSColor.whiteColor())
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        content.addSubview_(label)

        window.orderFront_(None)
        self.window = window
        self._dot_on = True

        # Pulse timer (also handles parent death check)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, objc.selector(self.pulse_, signature=b"v@:@"), None, True
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(self.timer, NSDefaultRunLoopMode)

        # Watch for parent process death in a thread
        self._parent_pid = os.getppid()
        watcher = threading.Thread(target=self._watch_parent, daemon=True)
        watcher.start()

    def _watch_parent(self):
        """Terminate when parent process dies."""
        import time
        while True:
            time.sleep(0.5)
            # Check if parent changed (reparented to init/launchd = parent died)
            if os.getppid() != self._parent_pid:
                self.app.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(None, selector=b"terminate:", signature=b"v@:@"),
                    None,
                    False,
                )
                break

    @objc.typedSelector(b"v@:@")
    def pulse_(self, timer):
        self._dot_on = not self._dot_on
        if self._dot_on:
            self.dot.setTextColor_(AppKit.NSColor.redColor())
        else:
            self.dot.setTextColor_(AppKit.NSColor.colorWithRed_green_blue_alpha_(0.4, 0.05, 0.03, 1.0))

    def run(self):
        self.app.run()


class RoundedView(AppKit.NSView):
    """A simple rounded-rect dark background view."""

    def drawRect_(self, rect):
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 12, 12)
        AppKit.NSColor.colorWithRed_green_blue_alpha_(0.1, 0.1, 0.1, 0.95).setFill()
        path.fill()


def main():
    overlay = OverlayWindow()
    overlay.run()


if __name__ == "__main__":
    main()
