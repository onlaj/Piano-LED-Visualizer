from webinterface import webinterface
from flask import render_template, flash, redirect, request, url_for, jsonify


@webinterface.route('/')
def index():
    return render_template('index.html')


@webinterface.route('/home')
def home():
    return render_template('home.html')


@webinterface.route('/ledsettings')
def ledsettings():
    return render_template('ledsettings.html')


@webinterface.route('/ledanimations')
def ledanimations():
    return render_template('ledanimations.html')

@webinterface.route('/songs')
def songs():
    return render_template('songs.html')

@webinterface.route('/sequences')
def sequences():
    return render_template('sequences.html')


@webinterface.route('/ports')
def ports():
    return render_template('ports.html')
