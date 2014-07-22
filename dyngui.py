#!/usr/bin/env python

from __future__ import print_function

import dolo
import sys
from collections import OrderedDict

from PyQt4.uic import loadUiType
from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QSettings
from PyQt4.QtCore import pyqtSignal as Signal
from PyQt4.QtCore import pyqtSlot as Slot
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QTextBlockFormat, QTextCursor
from PyQt4.QtCore import QFile

QTextBlockFormat
from PyQt4 import uic
engine = 'pyqt'

app = QtGui.QApplication(sys.argv)
app.setOrganizationName('DynGUI')
app.setOrganizationName('Pablo')

def readWidget(filename):
    f = QFile(filename)
    f.open(QFile.ReadOnly)

    if engine == 'pyside':
        loader = QUiLoader()
        myWidget = loader.load(f, self)
    else:
        myWidget = uic.loadUi(f)
    f.close()


    return myWidget


def highlight_line(textedit, line_number, color=None):


    # format.clearBackGround(Qt.yellow)
    cursor = QTextCursor(textedit.document().findBlockByNumber(line_number))
    fmt = QTextBlockFormat()

    if color is None:
        fmt.clearBackground()
        return
    if color == 'blue':
        fmt.setBackground(Qt.blue)
    elif color == 'red':
        fmt.setBackground(Qt.red)
    elif color == 'green':
        fmt.setBackground(Qt.green)
    if color == 'yellow':
        fmt.setBackground(Qt.yellow)
    elif color == 'magenta':
        fmt.setBackground(Qt.magenta)
    elif color == 'cyan':
        fmt.setBackground(Qt.cyan)

    cursor.setBlockFormat(fmt)



class MainWindow(QtGui.QMainWindow):
#    def accept(self):h
#        print 'hello'
#        self.eql.add_equation()
    current_file = None

    def __init__(self):

        QtGui.QMainWindow.__init__(self)

        self.ui = readWidget("modfile_editor.ui")

        self.make_connections()
        self.ui.show()

        self.open_file( 'rbc_dynare.yaml'  )

    def make_connections(self):
        self.ui.pushButton_2.clicked.connect(lambda : self.check())
        self.ui.pushButton.clicked.connect(lambda : self.solve())
        self.ui.pushButton.setEnabled(True)
        self.ui.actionOpen.triggered.connect(lambda : self.open_file())
        self.ui.actionSave.triggered.connect(lambda : self.save_file())


    def check(self):

        try:
            self.read_model()
            self.ui.pushButton.setEnabled(True)

        except Exception as e:
            print("Error found when trying to check the model:")
            print(e.__class__)
            print(e)
            self.ui.pushButton.setEnabled(False)


    def read_model(self):

        # construct model from the fields in the GUI
        equations = self.read_equations()
        [variables, parameters, shocks] = self.read_symbols()
        calibration = self.read_calibration()
        covs = self.read_covariances()

        from dolo.compiler.model_symbolic import SymbolicModel
        from dolo.compiler.model_dynare import DynareModel

        symbols = OrderedDict(
            variables = variables,
            shocks = shocks,
            parameters = parameters
        )
        name = 'anonymous'
        infos = dict(name=name, type='dynare')
        smodel = SymbolicModel( name, 'dynare', symbols, equations, calibration,
                     symbolic_covariances=covs, symbolic_markov_chain=None,
                      options=None, definitions=None)

        dmodel = DynareModel(smodel, infos=infos)

        import numpy
        # highlight lines with non-zero residuals
        y = dmodel.calibration['variables']
        e = dmodel.calibration['shocks']
        p = dmodel.calibration['parameters']
        res = dmodel.functions['f_static'](y,p)


        # quickly get a list of non-empty lines
        eqlines = str(self.ui.textEdit_equations.toPlainText()).split('\n')
        nonempty = [ (True if len(e.split('#')[0].strip())>0 else False)  for e in eqlines]
        ln = -1
        for i in range(len(res)):
            ln = nonempty.index(True, ln+1) # line number corresponding to equation
            if abs(res[i])>1e-6:
                highlight_line(self.ui.textEdit_equations, ln, 'cyan')
            else:
                highlight_line(self.ui.textEdit_equations, ln)


        from dolo.algos.dynare.perturbations import solve_decision_rule
        try:
            dr = solve_decision_rule(dmodel, order=1)
        except:
            raise Exception("Model incorrectly specified")

        return dmodel

    def solve(self):


        from dolo.algos.dynare.perturbations import solve_decision_rule

        order = self.ui.comboBox_order.currentIndex() + 1
        print(order)
        horizon = self.ui.spinBox_horizon.value()
        print(horizon)
        dmodel = self.read_model()

        dr = solve_decision_rule(dmodel, order=order)
        print(dr)


    def read_equations(self):

        textedit = self.ui.textEdit_equations
        # construct model from the fields in the GUI
        txt = textedit.toPlainText()

        import ast

        lines = txt.split('\n')
        equations = []
        errors = []
        for i,l in enumerate(lines):
            # we skip blank lines
            l = str(l)
            l = str.split(l, '#')[0] # remove commen"ts"
            l = l.replace("^", "**")
            if len(l.strip()) > 0:
                equations.append(l)
                # parse error
                try:

                    expr = ast.parse(l.replace("=",'==')).body[0].value
                except Exception:
                    highlight_line(textedit,i,'yellow')
                    # let's highlight line i
        return equations

    def read_symbols(self):

        text_variables = self.ui.lineEdit_variables.text()
        text_parameters = self.ui.lineEdit_parameters.text()
        text_shocks = self.ui.lineEdit_shocks.text()

        try:
            variables = str(text_variables).split(',')
            variables = [e.strip() for e in variables]
        except:
            return None
        try:
            parameters = str(text_parameters).split(',')
            parameters = [e.strip() for e in parameters]
        except:
            return None
        try:
            shocks = str(text_shocks).split(',')
            shocks = [e.strip() for e in shocks]
        except:
            return None

        return [variables, parameters, shocks]

    def read_calibration(self):

        import ast

        [variables, parameters, shocks] = self.read_symbols()

        calib_text = self.ui.textEdit_calibration.toPlainText()
        lines = calib_text.split('\n')
        d = OrderedDict()
        errors = []
        for i,l in enumerate(lines):
            # we skip blank lines
            l = str(l)
            l = str.split(l, '#')[0] # remove comments
            if len(l.strip()) > 0:
                try:
                    lhs, rhs = l.split('=')
                    key = lhs.strip()
                    rhs = rhs.strip()
                    d[key] = rhs.replace('^','**').strip()
                    ast.parse(rhs) # try to parse lhs just in case
                except Exception as err:
                    highlight_line(self.ui.textEdit_calibration, i, 'yellow')
                    errors.append([i, err])
        for s in shocks:
            d[s] = 0
        return d

    def read_covariances(self):

        table = self.ui.tableWidget_covariances
        n = table.columnCount()
        it = table.item(0,0)
        vals = []  #numpy.zeros(n,n, dtype=object)
        for i in range(n):
            line = []
            for j in range(n):
                v = (table.item(i,j))
                if v is None:
                    v = 0
                else:
                    v = str(v.text())
                line.append(v)
            vals.append(line)
        return vals


    def open_file(self, filename=None):

        if filename==None:
            filename = QtGui.QFileDialog.getOpenFileName()
            filename = str(filename)


        import yaml
        with open(filename) as f:
            txt = f.read()

        d = yaml.load(txt)
        self.ui.lineEdit_variables.setText(str.join(', ', d['symbols']['variables']))
        self.ui.lineEdit_shocks.setText(str.join(', ', d['symbols']['shocks']))
        self.ui.lineEdit_parameters.setText(str.join(', ', d['symbols']['parameters']))

        self.ui.textEdit_equations.setPlainText ( str.join('\n\n', d['equations']) )

        calib_text = ""
        for k,v in d['calibration'].iteritems():
            calib_text += '{} = {}\n'.format(k,v)

        self.ui.textEdit_calibration.setPlainText(calib_text)

    #
    # def save_file(self,filename):
    #
    #     filename = QtGui.QFileDialog.getSaveFileName()


window = MainWindow()
sys.exit(app.exec_())
