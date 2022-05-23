import pathlib
import unittest

from publish.junit import process_junit_xml_elems, ParsedUnitTestResults, UnitTestCase
from publish.xunit import parse_xunit_files

test_files_path = pathlib.Path(__file__).parent / 'files' / 'xunit'


class TestXunit(unittest.TestCase):
    def test_process_parse_xunit_files_with_time_factor(self):
        result_file = str(test_files_path / 'mstest' / 'pickles.xml')
        for time_factor in [1.0, 10.0, 60.0, 0.1, 0.001]:
            with self.subTest(time_factor=time_factor):
                actual = process_junit_xml_elems(parse_xunit_files([result_file]), time_factor=time_factor)
                self.assertEqual(actual,
                                 ParsedUnitTestResults(
                                     files=1,
                                     errors=[],
                                     suites=1,
                                     suite_tests=4,
                                     suite_skipped=0,
                                     suite_failures=1,
                                     suite_errors=0,
                                     suite_time=int(0.867 * time_factor),
                                     cases=[
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddingSeveralNumbers("60","70","130",System.String[])',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.137 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddingSeveralNumbers("40","50","90",System.String[])',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.009 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AdditionFeature.AddTwoNumbers',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.004 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AdditionFeature.FailToAddTwoNumbers',
                                             result='failure',
                                             content='\n'
                                                     'MESSAGE:\n'
                                                     '\n'
                                                     '+++++++++++++++++++\n'
                                                     'STACK TRACE:\n'
                                                     '\n'
                                                     '                        at Pickles.TestHarness.xUnit.Steps.ThenTheResultShouldBePass(Int32 result) in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.NUnit\\Steps.cs:line 26\nat lambda_method(Closure , IContextManager , Int32 )\n'
                                                     'at TechTalk.SpecFlow.Bindings.MethodBinding.InvokeAction(IContextManager contextManager, Object[] arguments, ITestTracer testTracer, TimeSpan& duration)\n'
                                                     'at TechTalk.SpecFlow.Bindings.StepDefinitionBinding.Invoke(IContextManager contextManager, ITestTracer testTracer, Object[] arguments, TimeSpan& duration)\n'
                                                     'at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStepMatch(BindingMatch match, Object[] arguments)\n'
                                                     'at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStep(StepArgs stepArgs)\n'
                                                     'at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.OnAfterLastStep()\n'
                                                     'at TechTalk.SpecFlow.TestRunner.CollectScenarioErrors()\n'
                                                     'at Pickles.TestHarness.AdditionFeature.ScenarioCleanup() in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.NUnit\\Addition.feature.cs:line 0\n'
                                                     'at Pickles.TestHarness.AdditionFeature.FailToAddTwoNumbers() in c:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.NUnit\\Addition.feature:line 18\n'
                                                     '\n'
                                                     '                      ',
                                             message=None,
                                             time=0.028 * time_factor
                                         )
                                     ]
                                 ))
