import pathlib
import unittest

from lxml import etree

from publish.junit import process_junit_xml_elems, ParsedUnitTestResults, UnitTestCase
from publish.xunit import parse_xunit_files, transform_xunit_to_junit

test_files_path = pathlib.Path(__file__).parent / 'files' / 'xunit'


class TestXunit(unittest.TestCase):
    def test_transform(self):
        result_file = str(test_files_path / 'mstest' / 'pickles.xml')
        trx = etree.parse(str(result_file))
        junit = transform_xunit_to_junit(trx)

        self.assertEqual(
            str(junit),
            '<testsuites>\n'
            '  <testsuite name="c:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\bin\\Debug\\Pickles.TestHarness.xUnit.dll" tests="4" failures="1" time="0.185" skipped="0" timestamp="2012-01-14T10:21:10">\n'
            '    <testsuite name="Pickles.TestHarness.xUnit.AdditionFeature" tests="4" failures="1" time="0.185" skipped="0">\n'
            '      <testcase name="AddTwoNumbers" time="0.153" classname="Pickles.TestHarness.xUnit.AdditionFeature"/>\n'
            '      <testcase name="AddingSeveralNumbers" time="0.006" classname="Pickles.TestHarness.xUnit.AdditionFeature"/>\n'
            '      <testcase name="AddingSeveralNumbers" time="0.003" classname="Pickles.TestHarness.xUnit.AdditionFeature"/>\n'
            '      <testcase name="FailToAddTwoNumbers" time="0.023" classname="Pickles.TestHarness.xUnit.AdditionFeature">\n'
            '        <failure type="System.InvalidOperationException" message="&#10;          System.InvalidOperationException : This is a fake failure message&#10;        "><![CDATA[\n'
            '          at Pickles.TestHarness.xUnit.Steps.ThenTheResultShouldBePass(Int32 result) in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\Steps.cs:line 26\n'
            '          at lambda_method(Closure , IContextManager , Int32 )\n'
            '          at TechTalk.SpecFlow.Bindings.MethodBinding.InvokeAction(IContextManager contextManager, Object[] arguments, ITestTracer testTracer, TimeSpan&amp; duration)\n'
            '          at TechTalk.SpecFlow.Bindings.StepDefinitionBinding.Invoke(IContextManager contextManager, ITestTracer testTracer, Object[] arguments, TimeSpan&amp; duration)\n'
            '          at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStepMatch(BindingMatch match, Object[] arguments)\n'
            '          at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStep(StepArgs stepArgs)\n'
            '          at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.OnAfterLastStep()\n'
            '          at TechTalk.SpecFlow.TestRunner.CollectScenarioErrors()\n'
            '          at Pickles.TestHarness.xUnit.AdditionFeature.ScenarioCleanup() in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\Addition.feature.cs:line 0\n'
            '          at Pickles.TestHarness.xUnit.AdditionFeature.FailToAddTwoNumbers() in c:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\Addition.feature:line 18\n'
            '        ]]></failure>\n'
            '      </testcase>\n'
            '    </testsuite>\n'
            '  </testsuite>\n'
            '</testsuites>\n'
        )

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
                                     suite_time=int(0.185 * time_factor),
                                     cases=[
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.xUnit.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddTwoNumbers',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.153 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.xUnit.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddingSeveralNumbers',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.006 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.xUnit.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='AddingSeveralNumbers',
                                             result='success',
                                             content=None,
                                             message=None,
                                             time=0.003 * time_factor
                                         ),
                                         UnitTestCase(
                                             class_name='Pickles.TestHarness.xUnit.AdditionFeature',
                                             result_file=result_file,
                                             test_file=None,
                                             line=None,
                                             test_name='FailToAddTwoNumbers',
                                             result='failure',
                                             content='<![CDATA[\n'
                                                     '          at Pickles.TestHarness.xUnit.Steps.ThenTheResultShouldBePass(Int32 result) in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\Steps.cs:line 26\n'
                                                     '          at lambda_method(Closure , IContextManager , Int32 )\n'
                                                     '          at TechTalk.SpecFlow.Bindings.MethodBinding.InvokeAction(IContextManager contextManager, Object[] arguments, ITestTracer testTracer, TimeSpan& duration)\n'
                                                     '          at TechTalk.SpecFlow.Bindings.StepDefinitionBinding.Invoke(IContextManager contextManager, ITestTracer testTracer, Object[] arguments, TimeSpan& duration)\n'
                                                     '          at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStepMatch(BindingMatch match, Object[] arguments)\n'
                                                     '          at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.ExecuteStep(StepArgs stepArgs)\n'
                                                     '          at TechTalk.SpecFlow.Infrastructure.TestExecutionEngine.OnAfterLastStep()\n'
                                                     '          at TechTalk.SpecFlow.TestRunner.CollectScenarioErrors()\n'
                                                     '          at Pickles.TestHarness.xUnit.AdditionFeature.ScenarioCleanup() in C:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\Addition.feature.cs:line 0\n'
                                                     '          at Pickles.TestHarness.xUnit.AdditionFeature.FailToAddTwoNumbers() in c:\\dev\\pickles-results-harness\\Pickles.TestHarness\\Pickles.TestHarness.xUnit\\Addition.feature:line 18\n'
                                                     '        ]]>',
                                             message='\n'
                                                     '          System.InvalidOperationException : This is a fake failure message\n        ',
                                             time=0.023 * time_factor
                                         )
                                     ]
                                 ))
