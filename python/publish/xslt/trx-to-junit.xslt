<?xml version="1.0" encoding="utf-8"?>
<!-- based on https://github.com/ekyoung/personal-site-dotnet/blob/7c2f6953960b9abf8d4f520ba0f257034b9a7371/trx-to-junit.xslt -->
<!-- and https://github.com/medlab/xunitparserx/blob/2cc8b68b0c5ce9c60da2934cb2cce10c8330536e/trx-to-junit.xslt -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:a="http://microsoft.com/schemas/VisualStudio/TeamTest/2006" xmlns:b="http://microsoft.com/schemas/VisualStudio/TeamTest/2010" >
  <xsl:output method="xml" indent="yes" />
  <xsl:template match="/">
    <testsuites>
      <xsl:variable name="numberOfTests" select="count(//a:UnitTestResult/@testId) + count(//b:UnitTestResult/@testId)"/>
      <xsl:variable name="numberOfFailures" select="count(//a:UnitTestResult/@outcome[.='Failed']) + count(//b:UnitTestResult/@outcome[.='Failed'])" />
      <xsl:variable name="numberOfErrors" select="count(//a:UnitTestResult[not(@outcome)]) + count(//b:UnitTestResult[not(@outcome)])" />
      <xsl:variable name="numberSkipped" select="count(//a:UnitTestResult/@outcome[.!='Passed' and .!='Failed']) + count(//b:UnitTestResult/@outcome[.!='Passed' and .!='Failed'])" />
      <testsuite name="MSTestSuite"
        tests="{$numberOfTests}"
        failures="{$numberOfFailures}"
        errors="{$numberOfErrors}"
        skipped="{$numberSkipped}">

        <xsl:for-each select="//a:UnitTestResult">
          <xsl:variable name="testName" select="@testName"/>
          <xsl:variable name="executionId" select="@executionId"/>
          <xsl:variable name="totalduration">
            <xsl:choose>
              <xsl:when test="@duration">
                <xsl:variable name="duration_seconds" select="substring(@duration, 7)"/>
                <xsl:variable name="duration_minutes" select="substring(@duration, 4,2 )"/>
                <xsl:variable name="duration_hours" select="substring(@duration, 1, 2)"/>
                <xsl:value-of select="format-number($duration_hours*3600 + $duration_minutes*60 + $duration_seconds, '#.#########')"/>
              </xsl:when>
              <xsl:when test="@startTime and @endTime">
                <xsl:variable name="d_seconds" select="substring(@endTime, 18,10) - substring(@startTime, 18,10)"/>
                <xsl:variable name="d_minutes" select="substring(@endTime, 15,2) - substring(@startTime, 15,2 )"/>
                <xsl:variable name="d_hours" select="substring(@endTime, 12,2) - substring(@startTime, 12, 2)"/>
                <xsl:value-of select="format-number($d_hours*3600 + $d_minutes*60 + $d_seconds, '#.#########')"/>
              </xsl:when>
              <xsl:otherwise>
                <xsl:value-of select="'0'"/>
              </xsl:otherwise>
            </xsl:choose>
          </xsl:variable>
          <xsl:variable name="outcome">
            <xsl:choose>
              <xsl:when test="@outcome">
                <xsl:value-of select="@outcome"/>
              </xsl:when>
              <xsl:otherwise>
                <xsl:value-of select="'Error'"/>
              </xsl:otherwise>
            </xsl:choose>
          </xsl:variable>
          <xsl:variable name="message" select="a:Output/a:ErrorInfo/a:Message"/>
          <xsl:variable name="stacktrace" select="a:Output/a:ErrorInfo/a:StackTrace"/>
          <xsl:for-each select="//a:UnitTest">
            <xsl:variable name="currentExecutionId" select="a:Execution/@id"/>
            <xsl:if test="$currentExecutionId = $executionId" >
              <xsl:variable name="className">
                <xsl:choose>
                  <xsl:when test="contains(a:TestMethod/@className, ',')">
                    <xsl:value-of select="substring-before(a:TestMethod/@className, ',')"/>
                  </xsl:when>
                  <xsl:otherwise>
                    <xsl:value-of select="a:TestMethod/@className"/>
                  </xsl:otherwise>
                </xsl:choose>
              </xsl:variable>
              <!-- sometimes $testName starts with $className: $className.$shortTestName-->
              <xsl:variable name="shortTestName">
                <xsl:choose>
                  <xsl:when test="starts-with($testName, concat($className, '.'))">
                    <xsl:value-of select="substring-after($testName, concat($className, '.'))"/>
                  </xsl:when>
                  <xsl:otherwise>
                    <xsl:value-of select="$testName"/>
                  </xsl:otherwise>
                </xsl:choose>
              </xsl:variable>
              <testcase classname="{$className}" name="{$shortTestName}" time="{$totalduration}">
                <xsl:if test="not(contains($outcome, 'Passed') or contains($outcome, 'Failed') or contains($outcome, 'Error'))">
                  <skipped>
                    <xsl:call-template name="result">
                      <xsl:with-param name="message" select="$message" />
                      <xsl:with-param name="stacktrace" as="" />
                    </xsl:call-template>
                  </skipped>
                </xsl:if>
                <xsl:if test="contains($outcome, 'Failed')">
                  <failure>
                    <xsl:call-template name="result">
                      <xsl:with-param name="message" select="$message" />
                      <xsl:with-param name="stacktrace" select="$stacktrace" />
                    </xsl:call-template>
                  </failure>
                </xsl:if>
                <xsl:if test="contains($outcome, 'Error')">
                  <error>
                    <xsl:call-template name="result">
                      <xsl:with-param name="message" select="$message" />
                      <xsl:with-param name="stacktrace" select="$stacktrace" />
                    </xsl:call-template>
                  </error>
                </xsl:if>
              </testcase>
            </xsl:if>
          </xsl:for-each>
        </xsl:for-each>

        <xsl:for-each select="//b:UnitTestResult">
          <xsl:variable name="testName" select="@testName"/>
          <xsl:variable name="executionId" select="@executionId"/>
          <xsl:variable name="testId" select="@testId"/>
          <xsl:variable name="totalduration">
            <xsl:choose>
              <xsl:when test="@duration">
                <xsl:variable name="duration_seconds" select="substring(@duration, 7)"/>
                <xsl:variable name="duration_minutes" select="substring(@duration, 4,2 )"/>
                <xsl:variable name="duration_hours" select="substring(@duration, 1, 2)"/>
                <xsl:value-of select="format-number($duration_hours*3600 + $duration_minutes*60 + $duration_seconds, '#.#########')"/>
              </xsl:when>
              <xsl:when test="@startTime and @endTime">
                <xsl:variable name="d_seconds" select="substring(@endTime, 18,10) - substring(@startTime, 18,10)"/>
                <xsl:variable name="d_minutes" select="substring(@endTime, 15,2) - substring(@startTime, 15,2 )"/>
                <xsl:variable name="d_hours" select="substring(@endTime, 12,2) - substring(@startTime, 12, 2)"/>
                <xsl:value-of select="format-number($d_hours*3600 + $d_minutes*60 + $d_seconds, '#.#########')"/>
              </xsl:when>
              <xsl:otherwise>
                <xsl:value-of select="'0'"/>
              </xsl:otherwise>
            </xsl:choose>
          </xsl:variable>
          <xsl:variable name="outcome">
            <xsl:choose>
              <xsl:when test="@outcome">
                <xsl:value-of select="@outcome"/>
              </xsl:when>
              <xsl:otherwise>
                <xsl:value-of select="'Error'"/>
              </xsl:otherwise>
            </xsl:choose>
          </xsl:variable>
          <xsl:variable name="message" select="b:Output/b:ErrorInfo/b:Message"/>
          <xsl:variable name="stacktrace" select="b:Output/b:ErrorInfo/b:StackTrace"/>
          <xsl:for-each select="//b:UnitTest">
            <xsl:variable name="currentTestId" select="@id"/>
            <xsl:if test="$currentTestId = $testId" >
              <xsl:variable name="className">
                <xsl:choose>
                  <xsl:when test="contains(b:TestMethod/@className, ',')">
                    <xsl:value-of select="substring-before(b:TestMethod/@className, ',')"/>
                  </xsl:when>
                  <xsl:otherwise>
                    <xsl:value-of select="b:TestMethod/@className"/>
                  </xsl:otherwise>
                </xsl:choose>
              </xsl:variable>
              <!-- sometimes $testName starts with $className: $className.$shortTestName-->
              <xsl:variable name="shortTestName">
                <xsl:choose>
                  <xsl:when test="starts-with($testName, concat($className, '.'))">
                    <xsl:value-of select="substring-after($testName, concat($className, '.'))"/>
                  </xsl:when>
                  <xsl:otherwise>
                    <xsl:value-of select="$testName"/>
                  </xsl:otherwise>
                </xsl:choose>
              </xsl:variable>
              <testcase classname="{$className}" name="{$shortTestName}" time="{$totalduration}">
                <xsl:if test="not(contains($outcome, 'Passed') or contains($outcome, 'Failed') or contains($outcome, 'Error'))">
                  <skipped>
                    <xsl:call-template name="result">
                      <xsl:with-param name="message" select="$message" />
                      <xsl:with-param name="stacktrace" as="" />
                    </xsl:call-template>
                  </skipped>
                </xsl:if>
                <xsl:if test="contains($outcome, 'Failed')">
                  <failure>
                    <xsl:call-template name="result">
                      <xsl:with-param name="message" select="$message" />
                      <xsl:with-param name="stacktrace" select="$stacktrace" />
                    </xsl:call-template>
                  </failure>
                </xsl:if>
                <xsl:if test="contains($outcome, 'Error')">
                  <error>
                    <xsl:call-template name="result">
                      <xsl:with-param name="message" select="$message" />
                      <xsl:with-param name="stacktrace" select="$stacktrace" />
                    </xsl:call-template>
                  </error>
                </xsl:if>
              </testcase>
            </xsl:if>
          </xsl:for-each>
        </xsl:for-each>

      </testsuite>
    </testsuites>
  </xsl:template>

  <xsl:template name="result">
    <xsl:param name="message"/>
    <xsl:param name="stacktrace"/>
    <xsl:attribute name="message"><xsl:value-of select="$message"/></xsl:attribute>
    <xsl:value-of select="$message"/>
    <xsl:value-of select="$stacktrace"/>
  </xsl:template>

</xsl:stylesheet>
