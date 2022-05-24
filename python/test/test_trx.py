import pathlib
import unittest

from lxml import etree

from publish.junit import process_junit_xml_elems, ParsedUnitTestResults, UnitTestCase
from publish.trx import parse_trx_files, transform_trx_to_junit

test_files_path = pathlib.Path(__file__).parent / 'files'


class TestTrx(unittest.TestCase):

    def test_transform(self):
        result_file = str(test_files_path / 'mstest.trx')
        trx = etree.parse(str(result_file))
        junit = transform_trx_to_junit(trx)

        self.assertEqual(
            str(junit),
            '<?xml version="1.0"?>\n'
            '<testsuites xmlns:a="http://microsoft.com/schemas/VisualStudio/TeamTest/2006" xmlns:b="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">\n'
            '  <testsuite name="MSTestSuite" tests="4" failures="1" errors="0" skipped="0">\n'
            '    <testcase classname="Pickles.TestHarness.MSTest.AdditionFeature" name="AddingSeveralNumbers_40" time="0.076891"/>\n'
            '    <testcase classname="Pickles.TestHarness.MSTest.AdditionFeature" name="AddingSeveralNumbers_60" time="0.0111534"/>\n'
            '    <testcase classname="Pickles.TestHarness.MSTest.AdditionFeature" name="AddTwoNumbers" time="0.0055623"/>\n'
            '    <testcase classname="Pickles.TestHarness.MSTest.AdditionFeature" name="FailToAddTwoNumbers" time="0.0459057">\n'
            '      <failure>\n'
            '                    MESSAGE:\n'
            '                    \n'
            '            Test method Pickles.TestHarness.MSTest.AdditionFeature.FailToAddTwoNumbers threw exception:\n'
            '            Should.Core.Exceptions.NotEqualException: Assert.NotEqual() Failure\n'
            '          \n'
            '                    +++++++++++++++++++\n'
            '                    STACK TRACE:\n'
            '                    \n'
            '            at Pickles.TestHarness.MSTest.Steps.ThenTheResultShouldBePass(Int32 result) in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.MSTest\\Steps.cs:line 28\n'
            '            at lambda_method(Closure , IContextManager , Int32 )\n'
            '            at TechTalk.SpecFlow.Bindings.MethodBinding.InvokeAction(IContextManager contextManager, Object[] arguments, ITestTracer testTracer, TimeSpan&amp; duration)\n'
            '            at TechTalk.SpecFlow.Bindings.StepDefinitionBinding.Invoke(IContextManager contextManager, ITestTracer testTracer, Object[] arguments, TimeSpan&amp; duration)\n'
            '            at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStepMatch(BindingMatch match, Object[] arguments)\n'
            '            at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStep(StepArgs stepArgs)\n'
            '            at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.OnAfterLastStep()\n'
            '            at TechTalk.SpecFlow.TestRunner.CollectScenarioErrors()\n'
            '            at Pickles.TestHarness.MSTest.AdditionFeature.ScenarioCleanup() in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.MSTest\\Addition.feature.cs:line 0\n'
            '            at Pickles.TestHarness.MSTest.AdditionFeature.FailToAddTwoNumbers() in c:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.MSTest\\Addition.feature:line 18\n'
            '          </failure>\n'
            '    </testcase>\n'
            '  </testsuite>\n'
            '</testsuites>\n'
        )

    def test_process_parse_trx_files_with_time_factor(self):
        result_file = str(test_files_path / 'mstest.trx')
        for time_factor in [1.0, 10.0, 60.0, 0.1, 0.001]:
            with self.subTest(time_factor=time_factor):
                actual = process_junit_xml_elems(parse_trx_files([result_file]), time_factor=time_factor)
                self.assertEqual(actual,
                                 ParsedUnitTestResults(
                                     files=1,
                                     errors=[],
                                     suites=1,
                                     suite_tests=4,
                                     suite_skipped=0,
                                     suite_failures=1,
                                     suite_errors=0,
                                     suite_time=int(0.1395124 * time_factor),
                                     cases=[
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.MSTest.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddingSeveralNumbers_40',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.076891 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.MSTest.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddingSeveralNumbers_60',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.0111534 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.MSTest.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddTwoNumbers',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.0055623 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.MSTest.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='FailToAddTwoNumbers',
                                             result='failure',
                                             content='\n'
                                                     '                    MESSAGE:\n'
                                                     '                    \n'
                                                     '            Test method Pickles.TestHarness.MSTest.AdditionFeature.FailToAddTwoNumbers threw exception:\n'
                                                     '            Should.Core.Exceptions.NotEqualException: Assert.NotEqual() Failure\n'
                                                     '          \n'
                                                     '                    +++++++++++++++++++\n'
                                                     '                    STACK TRACE:\n'
                                                     '                    \n'
                                                     '            at Pickles.TestHarness.MSTest.Steps.ThenTheResultShouldBePass(Int32 result) in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.MSTest\\Steps.cs:line 28\n'
                                                     '            at lambda_method(Closure , IContextManager , Int32 )\n'
                                                     '            at TechTalk.SpecFlow.Bindings.MethodBinding.InvokeAction(IContextManager contextManager, Object[] arguments, ITestTracer testTracer, TimeSpan& duration)\n'
                                                     '            at TechTalk.SpecFlow.Bindings.StepDefinitionBinding.Invoke(IContextManager contextManager, ITestTracer testTracer, Object[] arguments, TimeSpan& duration)\n'
                                                     '            at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStepMatch(BindingMatch match, Object[] arguments)\n'
                                                     '            at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStep(StepArgs stepArgs)\n'
                                                     '            at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.OnAfterLastStep()\n'
                                                     '            at TechTalk.SpecFlow.TestRunner.CollectScenarioErrors()\n'
                                                     '            at Pickles.TestHarness.MSTest.AdditionFeature.ScenarioCleanup() in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.MSTest\\Addition.feature.cs:line 0\n'
                                                     '            at Pickles.TestHarness.MSTest.AdditionFeature.FailToAddTwoNumbers() in c:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.MSTest\\Addition.feature:line 18\n'
                                                     '          ',
                                             message=None,
                                             time=0.0459057 * time_factor
                                         )
                                     ]
                                 ))
