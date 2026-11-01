<?php
use PhpOffice\PhpSpreadsheet\Calculation\Logical\Boolean;

/**
 * * COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : antonio
 *
 * This file is part of ProjeQtOr.
 *
 * ProjeQtOr is free software: you can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option)
 * any later version.
 *
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org
 *
 * ** DO NOT REMOVE THIS NOTICE ***********************************************
 */

/**
 * ===========================================================================**********
 * Abstract class defining all methods to interact with database,
 * using Sql class.
 * Give public visibility to elementary methods (save, delete, copy, ...)
 * and constructor.
 */
if (file_exists('../_securityCheck.php')) include_once ('../_securityCheck.php');

#[AllowDynamicProperties]
abstract class SqlElement {

  // List of fields that will be exposed in general user interface
  public $id;

  // every SqlElement have an id !!!
  public static $_evaluationString='###EVAL###';

  public static $_evaluationStringForbiddenKeywords=array(
      'paramDb',
      'getGlobalParameter',
      'readfile',
      'exit',
      'fopen',
      'fsockopen',
      'copy',
      'move',
      'kill',
      'file_get_contents',
      'include',
      'stream_context_create');

  private static $_copyInProgress=false;

  public static $_skipWorkflowControl=false;

  public static $_skipProjectControl=false;

  public static $_skipAllControls=false;

  // Equivalent to force=1
  private static $staticCostVisibility=null;

  private static $staticWorkVisibility=null;

  private static $staticDeleteConfirmed=false;

  private static $staticSaveConfirmed=false;

  // Store the layout of the different object classes
  private static $_tablesFormatList=array();

  private static $_tablesFormatListColumns=array();

  private static $_fieldsLists=array();

  // Define the layout that will be used for lists
  private static $_layout='
    <th field="id" formatter="numericFormatter" width="10%"># ${id}</th>
    <th field="name" width="85%">${name}</th> 
    <th field="idle" width="5%" formatter="booleanFormatter">${idle}</th>
    ';

  // Define the specific field attributes
  private static $_fieldsAttributes=array("name"=>"required");

  // BEGIN - ADD BY TABARY - TOOLTIP
  private static $_fieldsTooltip=array();

  // END - ADD BY TABARY - TOOLTIP
  private static $_defaultValues=array();

  public static $_doNotSaveLastUpdateDateTime=false;

  public static $_deletedObject=array();

  // Management of cache for queries : cache is only valid during current script
  public static $_cachedQuery=array(
      'AccessProfile'=>array(),
      'AccessProfileAll'=>array(),
      'AccessProfileNoProject'=>array(),
      'AccessProfileNoProjectSimple'=>array(),
      'AccessRight'=>array(),
      'AccessScope'=>array(),
      'Checklistable'=>array(),
      'Habilitation'=>array(),
      'HabilitationOther'=>array(),
      'HabilitationReport'=>array(),
      'Menu'=>array(),
      'PluginTriggeredEvent'=>array(),
      'Plugin'=>array(),
      'RestrictList'=>array());

  // Management of extraHiddenFileds per type, status or profile
  private static $_extraHiddenFields=null;

  // Management of extraReadonlyFileds per type, status or profile
  private static $_extraReadonlyFields=null;

  // Management of extraRequiredFileds per type, status or profile
  private static $_extraRequiredFields=null;

  // ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
  // Management of drawing spinner for a field
  // Array :
  // - key : Name of the field
  // - value : Attributes of spinner.
  // For each attribute : String separated by commas : 'attribute of spinner:value,'
  // Attributes are :
  // - min : Minimal value of spinner (default = 0)
  // - max : Maximal value of spinner (default = 100)
  // - step : Step of increment (default = 1)
  // - bkColor : Span on right with this background color
  // Sample : $_spinnersAttributes = array(
  // "year"=>"min:2000,max:2100,step:1"
  // );
  private static $_spinnersAttributes=array();

  // END ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER

  // ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
  // Fields list that must be disabled when something changes on form detail
  // Avalable for fields :
  // - in widget (dijit)
  // - specific ('_spe_') that have an id in DOM that respect the following naming rule :
  // id_[name of the field without _spe_] ex : field with name _spe_theSpecificField must have this id in DOM id__theSpecificField
  // If the specific field has in it name 'button' (case insensitive) then it will be hidden else it will be readonly
  // getStaticDisabledFieldOnChange et getDisabledFieldOnChange must be implemented on this class
  // See implementation in OrganizationBudgetElementMain
  private static $_disabledFieldsOnChange=array();

  // END ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET

  // All dependencies between objects :
  // control => sub-object must not exist to allow deletion
  // cascade => sub-objects are automaticaly deleted
  // confirm => confirmation will be requested
  private static $_relationShip=array(
      "AccessProfile"=>array("AccessRight"=>"controlStrict"),
      "AccessProfileNoProject"=>array("AccessRight"=>"controlStrict"),
      "AccessScope"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeNoProject"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeRead"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeCreate"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeUpdate"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeDelete"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeNoProjectRead"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeNoProjectCreate"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeNoProjectUpdate"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "AccessScopeNoProjectDelete"=>array("AccessProfile"=>"controlStrict", "AccessProfileNoProject"=>"controlStrict"),
      "Asset"=>array("ProductAsset"=>"cascade"),
      "AssetCategory"=>array("Asset"=>"controlStrict"),
      "Acceptance"=>array("WorkCommandAccepted"=>"cascade"),
      "Assignment"=>array(
          "AssignmentRecurring"=>"cascade",
          "PlannedWork"=>"cascade",
          "PokerResource"=>"cascade",
          "Work"=>"controlStrict"),
      "Action"=>array("Attachment"=>"cascade", "Link"=>"cascade", "Note"=>"cascade", "SubTask"=>"cascade"),
      "ActionType"=>array("Action"=>"controlStrict"),
      "Activity"=>array(
          "Activity"=>"confirm",
          "Assignment"=>"confirm",
          "Attachment"=>"cascade",
          "Dependency"=>"cascade",
          "Link"=>"cascade",
          "Meeting"=>"confirm",
          "Milestone"=>"confirm",
          "Note"=>"cascade",
          "PeriodicMeeting"=>"confirm",
          "PlannedWork"=>"cascade",
          "TestSession"=>"confirm",
          "Ticket"=>"control",
          "SubTask"=>"cascade"),
      "ActivityType"=>array("Activity"=>"controlStrict"),
      "Bill"=>array("BillLine"=>"confirm", "Note"=>"cascade", "Situation"=>"cascade"),
      "BillType"=>array("Bill"=>"controlStrict"),
      "Brand"=>array("Asset"=>"controlStrict", "Model"=>"controlStrict"),
      "CallForTender"=>array("Tender"=>"controlStrict", "TenderEvaluationCriteria"=>"cascade", "Situation"=>"cascade"),
      "CallForTenderType"=>array("CallForTender"=>"controlStrict"),
      "CalendarDefinition"=>array("Calendar"=>"cascade", "Resource"=>"controlStrict"),
      "CatalogUO"=>array("Complexity"=>"cascade", "WorkUnit"=>"cascade"),
      "Checklist"=>array("ChecklistLine"=>"cascade"),
      "ChecklistDefinition"=>array("Checklist"=>"control", "ChecklistDefinitionLine"=>"cascade"),
      "ClientContract"=>array("WorkTokenClientContract"=>"control"),
      "ClientType"=>array("Client"=>"controlStrict"),
      "Command"=>array(
          "Attachment"=>"cascade",
          "Link"=>"cascade",
          "Note"=>"cascade",
          "WorkCommand"=>"cascade",
          "Situation"=>"cascade"),
      "CommandType"=>array("Command"=>"controlStrict"),
      "Component"=>array("ProductStructure"=>"cascade", "ComponentVersion"=>"control"),
      "ComponentVersion"=>array(
          "Requirement"=>"control",
          "TestCase"=>"control",
          "TestSession"=>"control",
          "Ticket"=>"control",
          "ProductAsset"=>"cascade"),
      "Complexity"=>array("ComplexityValues"=>"cascade"),
      "Contact"=>array(
          "Activity"=>"controlStrict",
          "Affectation"=>"confirm",
          "Bill"=>"controlStrict",
          "Product"=>"controlStrict",
          "Project"=>"controlStrict",
          "Tender"=>"ControlStrict",
          "Ticket"=>"controlStrict",
          "Version"=>"controlStrict"),
      "ContextType"=>array("Context"=>"controlStrict"),
      "Client"=>array("Project"=>"control"),
      "Criticality"=>array(
          "Issue"=>"controlStrict",
          "Opportunity"=>"controlStrict",
          "Requirement"=>"controlStrict",
          "Risk"=>"controlStrict",
          "Ticket"=>"controlStrict"),
      "Decision"=>array("Attachment"=>"cascade", "Link"=>"cascade", "Note"=>"cascade"),
      "DecisionType"=>array("Decision"=>"controlStrict"),
      "Document"=>array("Approver"=>"control", "DocumentVersion"=>"control", "Link"=>"cascade", "Note"=>"cascade"),
      "DocumentVersion"=>array("Approver"=>"cascade"),
      "DocumentDirectory"=>array("Document"=>"control", "DocumentDirectory"=>"control", "DocumentRight"=>"cascade"),
      "DocumentType"=>array("Document"=>"controlStrict"),
      "Efficiency"=>array("Action"=>"controlStrict"),
      // MTY - LEAVE SYSTEM
      "Employee"=>array("EmployeeLeaveEarned"=>"control", "Leave"=>"control", "EmploymentContract"=>"control"),
      "EmploymentContractEndReason"=>array("EmploymentContract"=>"controlStrict"),
      "EmploymentContractType"=>array(
          "EmploymentContract"=>"controlStrict",
          "CustomEarnedRulesOfEmploymentContractType"=>"control",
          "LeaveTypeOfEmploymentContractType"=>"control"),
      // MTY - LEAVE SYSTEM
      "ExpenseDetailType"=>array("ExpenseDetail"=>"controlStrict"),
      "Feasibility"=>array("Requirement"=>"controlStrict"),
      "Filter"=>array("FilterCriteria"=>"cascade"),
      "Health"=>array("Project"=>"controlStrict"),
      "IndividualExpenseType"=>array("IndividualExpense"=>"controlStrict"),
      "Issue"=>array("Attachment"=>"cascade", "Link"=>"cascade", "Note"=>"cascade"),
      "IssueType"=>array("Issue"=>"controlStrict"),
      "JoblistDefinition"=>array("Job"=>"control", "JobDefinition"=>"cascade"),
      // MTY - LEAVE SYSTEM
      "Leave"=>array("work"=>"cascade", "plannedWork"=>"cascade"),
      "LeaveType"=>array(
          "Leave"=>"confirm",
          "CustomEarnedRulesOfEmploymentContractType"=>"confirm",
          "LeaveTypeOfEmploymentContractType"=>"confirm" // "EmployeeLeaveEarned" => "confirm",
      ),
      // MTY - LEAVE SYSTEM
      "Likelihood"=>array("Opportunity"=>"controlStrict", "Risk"=>"controlStrict"),
      "Location"=>array("Asset"=>"controlStrict"),
      "Meeting"=>array(
          "Assignment"=>"cascade",
          "Attachment"=>"cascade",
          "Dependency"=>"cascade",
          "Link"=>"cascade",
          "Note"=>"cascade",
          "PlannedWork"=>"cascade"),
      "MeetingType"=>array("Meeting"=>"controlStrict", "PeriodicMeeting"=>"controlStrict"),
      "Menu"=>array("AccessRight"=>"cascade"),
      "MessageLegal"=>array("MessageLegalFollowup"=>"confirm"),
      "MessageType"=>array("Message"=>"controlStrict"),
      "Milestone"=>array("Attachment"=>"cascade", "Dependency"=>"cascade", "Link"=>"cascade", "Note"=>"cascade"),
      "MilestoneType"=>array("Milestone"=>"controlStrict"),
      "Model"=>array("Brand"=>"controlStrict", "Asset"=>"controlStrict"),
      "Notifiable"=>array("NotificationDefinition"=>"controlStrict", "Notification"=>"controlStrict"),
      "NotificationDefinition"=>array("Notification"=>"controlStrict"),
      "OverallProgress"=>array("Project"=>"controlStrict"),
      "OpportunityType"=>array("Opportunity"=>"controlStrict"),
      "Organization"=>array(
          "Attachment"=>"cascade",
          "Link"=>"cascade",
          "Note"=>"cascade",
          "BudgetElement"=>"cascade",
          "Project"=>"controlStrict",
          "Organization"=>"control",
          "Resource"=>"controlStrict"),
      "PaymentType"=>array("Payment"=>"controlStrict"),
      "PeriodicMeeting"=>array("Assignment"=>"cascade", "Meeting"=>"cascade", "Note"=>"cascade"),
      "PokerItem"=>array("PokerVote"=>"cascade"),
      "Priority"=>array(
          "Action"=>"controlStrict",
          "Issue"=>"controlStrict",
          "Opportunity"=>"controlStrict",
          "Risk"=>"controlStrict",
          "TestCase"=>"controlStrict",
          "Ticket"=>"controlStrict"),
      "Profile"=>array(
          "AccessRight"=>"cascade",
          "Habilitation"=>"cascade",
          "Message"=>"cascade",
          "Resource"=>"controlStrict",
          "User"=>"controlStrict",
          "DocumentRight"=>"cascade"),
      "ProjectExpenseType"=>array("ProjectExpense"=>"controlStrict"),
      "ProjectType"=>array("Project"=>"controlStrict"),
      "Product"=>array(
          "Component"=>"cascade",
          "Requirement"=>"control",
          "TestCase"=>"control",
          "TestSession"=>"control",
          "ProductVersion"=>"control"),
      "ProductVersion"=>array(
          "Requirement"=>"control",
          "TestCase"=>"control",
          "TestSession"=>"control",
          "VersionProject"=>"cascade",
          "Ticket"=>"control",
          "Activity"=>"control",
          "ProductAsset"=>"cascade"),
      "Profile"=>array(
          "Resource"=>"controlStrict",
          "User"=>"controlStrict",
          "Contact"=>"controlStrict",
          "Affectation"=>"controlStrict"),
      "Project"=>array(
          "Action"=>"control",
          "Activity"=>"confirm",
          "Affectation"=>"confirm",
          "Assignment"=>"cascade",
          "Attachment"=>"cascade",
          "Bill"=>"control",
          "CallForTender"=>"control",
          "Command"=>"control",
          "Decision"=>"control",
          "Dependency"=>"cascade",
          "Document"=>"control",
          "IndicatorDefinitionPerProject"=>"cascade",
          "Issue"=>"control",
          "IndividualExpense"=>"control",
          "Link"=>"cascade",
          "Meeting"=>"confirm",
          "Message"=>"cascade",
          "Milestone"=>"confirm",
          "Note"=>"cascade",
          "Opportunity"=>"control",
          "Parameter"=>"cascade",
          "PeriodicMeeting"=>"confirm",
          "PlannedWork"=>"cascade",
          "Project"=>"confirm",
          "ProjectExpense"=>"control",
          "ProjectSituation"=>"cascade",
          "ProviderBill"=>"control",
          "ProviderOrder"=>"control",
          "Requirement"=>"control",
          "Risk"=>"control",
          "Question"=>"control",
          "Quotation"=>"control",
          "StatusMailPerProject"=>"cascade",
          "Tender"=>"control",
          "Term"=>"control",
          "TestCase"=>"control",
          "TestSession"=>"confirm",
          "Ticket"=>"control",
          "TicketDelayPerProject"=>"cascade",
          "VersionProject"=>"cascade",
          "TokenDefinition"=>"control",
          "Work"=>"controlStrict"),
      "Provider"=>array("ProjectExpense"=>"controlStrict", "Tender"=>"ControlStrict", "Situation"=>"cascade"),
      "ProviderBill"=>array("BillLine"=>"cascade", "ProviderTerm"=>"controlStrict", "Situation"=>"cascade"),
      "ProviderOrder"=>array("BillLine"=>"cascade", "ProviderTerm"=>"controlStrict", "Situation"=>"cascade"),
      "ProviderTerm"=>array("BillLine"=>"cascade"),
      "Quality"=>array("Project"=>"controlStrict"),
      "Question"=>array("Link"=>"cascade"),
      "QuestionType"=>array("Question"=>"controlStrict"),
      "Quotation"=>array("Attachment"=>"cascade", "Link"=>"cascade", "Note"=>"cascade", "Situation"=>"cascade"),
      "QuotationType"=>array("Quotation"=>"controlStrict"),
      "Recipient"=>array("Bill"=>"control", "Project"=>"controlStrict"),
      "Report"=>array(
          "ReportParameter"=>"cascade",
          "HabilitationReport"=>"cascade",
          "AutoSendReport"=>"cascade",
          "Today"=>"cascade",
          "TodayParameter"=>"cascade",
          "Favorite"=>"cascade",
          "FavoriteParameter"=>"cascade",
          "Navigation"=>"cascade"),
      "RequirementType"=>array("Requirement"=>"controlStrict"),
      "Requirement"=>array("Attachment"=>"cascade", "Link"=>"cascade", "Note"=>"cascade", "Requirement"=>"control"),
      "Resolution"=>array("Ticket"=>"controlStrict"),
      "Resource"=>array(
          "Action"=>"controlStrict",
          "Activity"=>"controlStrict",
          "Affectation"=>"confirm",
          "Assignment"=>"control",
          "CallForTender"=>"controlStrict",
          "Decision"=>"controlStrict",
          "Issue"=>"controlStrict",
          "Meeting"=>"controlStrict",
          "Milestone"=>"controlStrict",
          "Question"=>"controlStrict",
          "Requirement"=>"controlStrict",
          "ResourceCost"=>"cascade",
          "Risk"=>"controlStrict",
          "Ticket"=>"controlStrict",
          "Tender"=>"controlStrict",
          "TestCase"=>"controlStrict",
          "TestSession"=>"controlStrict",
          "Work"=>"controlStrict",
          "ResourceTeamAffectation"=>"confirm"),
      "ResourceTeam"=>array("Affectation"=>"confirm", "Assignment"=>"controlStrict", "ResourceTeamAffectation"=>"cascade"),
      "Risk"=>array("Attachment"=>"cascade", "Link"=>"cascade", "Note"=>"cascade"),
      "RiskLevel"=>array("Requirement"=>"controlStrict"),
      "RiskType"=>array("Risk"=>"controlStrict"),
      "Role"=>array(
          "Affectation"=>"controlStrict",
          "Assignment"=>"controlStrict",
          "Resource"=>"controlStrict",
          "ResourceCost"=>"controlStrict"),
      "Severity"=>array("Opportunity"=>"controlStrict", "Risk"=>"controlStrict"),
      "Skill"=>array("ResourceSkill"=>"controlStrict", "ActivitySkill"=>"controlStrict"),
      "Status"=>array(
          "Action"=>"controlStrict",
          "Activity"=>"controlStrict",
          "Asset"=>"controlStrict",
          "Bill"=>"controlStrict",
          "Budget"=>"controlStrict",
          "CallForTender"=>"controlStrict",
          "ChangeRequest"=>"controlStrict",
          "ClientContract"=>"controlStrict",
          "Command"=>"controlStrict",
          "Component"=>"controlStrict",
          "ComponentVersion"=>"controlStrict",
          "Decision"=>"controlStrict",
          "Delivery"=>"controlStrict",
          "Document"=>"controlStrict",
          "DocumentVersion"=>"controlStrict",
          "EmploymentContract"=>"controlStrict",
          // "Expense" => "controlStrict",
          "IndividualExpense"=>"controlStrict",
          "Issue"=>"controlStrict",
          // MTY - LEAVE SYSTEM
          "Leave"=>"controlStrict",
          // MTY - LEAVE SYSTEM
          "LocalizationItem"=>"controlStrict",
          "LocalizationRequest"=>"controlStrict",
          "Mail"=>"controlStrict",
          "Meeting"=>"controlStrict",
          "Milestone"=>"controlStrict",
          // "Notification" => "controlStrict",
          "Opportunity"=>"controlStrict",
          "PokerSession"=>"controlStrict",
          "PredefinedAction"=>"controlStrict",
          "Product"=>"controlStrict",
          "ProductOrComponent"=>"controlStrict",
          "ProductVersion"=>"controlStrict",
          "Project"=>"controlStrict",
          "ProjectExpense"=>"controlStrict",
          "ProviderBill"=>"controlStrict",
          "ProviderOrder"=>"controlStrict",
          "Question"=>"controlStrict",
          "Quotation"=>"controlStrict",
          "Requirement"=>"controlStrict",
          "Risk"=>"controlStrict",
          "StatusMail"=>"controlStrict",
          "SupplierContract"=>"controlStrict",
          "Tender"=>"controlStrict",
          "TestCase"=>"controlStrict",
          "TestSession"=>"controlStrict",
          "Ticket"=>"controlStrict",
          "WorkflowStatus"=>"cascade"),
      "SubTask"=>array("Attachment"=>"cascade"),
      "Team"=>array("Resource"=>"control"),
      "Tender"=>array("TenderEvaluation"=>"cascade", "Situation"=>"cascade"),
      "TenderStatus"=>array("Tender"=>"control"),
      "TenderType"=>array("Tender"=>"control"),
      "Term"=>array("Dependency"=>"cascade"),
      "TestCase"=>array("TestCase"=>"control", "TestCaseRun"=>"control"),
      "TestCaseType"=>array("TestCase"=>"controlStrict"),
      "TestSession"=>array(
          "Assignment"=>"confirm",
          "Attachment"=>"cascade",
          "Dependency"=>"cascade",
          "Link"=>"cascade",
          "Note"=>"cascade",
          "PlannedWork"=>"cascade",
          "TestCaseRun"=>"cascade"),
      "TestSessionType"=>array("TestSession"=>"controlStrict"),
      "Ticket"=>array(
          "Attachment"=>"cascade",
          "Link"=>"cascade",
          "Note"=>"cascade",
          "Ticket"=>"control",
          "Work"=>"control",
          "SubTask"=>"cascade"),
      "TicketType"=>array("Ticket"=>"controlStrict"),
      "TokenDefinition"=>array("WorkTokenMarkup"=>"cascade"),
      "Trend"=>array("Project"=>"controlStrict"),
      "Urgency"=>array(
          "Delay"=>"controlStrict",
          "Requirement"=>"controlStrict",
          "Ticket"=>"controlStrict",
          "TicketDelay"=>"controlStrict"),
      "User"=>array(
          "Action"=>"controlStrict",
          "Activity"=>"controlStrict",
          "Affectation"=>"confirm",
          "Attachment"=>"control",
          "Command"=>"controlStrict",
          "Decision"=>"controlStrict",
          "Issue"=>"controlStrict",
          "Meeting"=>"controlStrict",
          "Message"=>"control",
          "Milestone"=>"controlStrict",
          "Note"=>"control",
          "Opportunity"=>"controlStrict",
          "Parameter"=>"cascade",
          "Project"=>"controlStrict",
          "Question"=>"controlStrict",
          "Quotation"=>"controlStrict",
          "Requirement"=>"controlStrict",
          "Risk"=>"controlStrict",
          "TestCase"=>"controlStrict",
          "TestSession"=>"controlStrict",
          "Ticket"=>"controlStrict",
          "VotingAttribution"=>"confirm"),
      "Version"=>array("Requirement"=>"control", "TestCase"=>"control", "TestSession"=>"control", "VersionProject"=>"cascade"),
      // "VersioningType" => array("Versioning" => "controlStrict"),
      "Work"=>array("WorkTokenClientContractWork"=>"cascade"),
      "WorkElement"=>array("Work"=>"cascade"),
      "WorkUnit"=>array("ComplexityValues"=>"cascade"),
      "Workflow"=>array(
          "ActionType"=>"controlStrict",
          "ActivityType"=>"controlStrict",
          "BillType"=>"controlStrict",
          "ClientType"=>"controlStrict",
          "CommandType"=>"controlStrict",
          // "ContextType"=>"controlStrict",
          "DecisionType"=>"controlStrict",
          "DocumentType"=>"controlStrict",
          // "ExpenseDetailType"=>"controlStrict",
          "IndividualExpenseType"=>"controlStrict",
          "IssueType"=>"controlStrict",
          "TicketType"=>"controlStrict",
          "MeetingType"=>"controlStrict",
          "MessageType"=>"controlStrict",
          "OpportunityType"=>"controlStrict",
          "PaymentType"=>"controlStrict",
          "ProjectExpenseType"=>"controlStrict",
          "ProjectType"=>"controlStrict",
          "QuestionType"=>"controlStrict",
          "QuotationType"=>"controlStrict",
          "RequirementType"=>"controlStrict",
          "MilestoneType"=>"controlStrict",
          "RiskType"=>"controlStrict",
          "TestCaseType"=>"controlStrict",
          "TestSessionType"=>"controlStrict",
          "VersioningType"=>"controlStrict",
          "WorkflowStatus"=>"cascade"));

  private static $_closeRelationShip=array(
      "AccessScopeRead"=>array("AccessProfile"=>"control"),
      "AccessScopeCreate"=>array("AccessProfile"=>"control"),
      "AccessScopeUpdate"=>array("AccessProfile"=>"control"),
      "AccessScopeDelete"=>array("AccessProfile"=>"control"),
      "Activity"=>array(
          "Assignment"=>"cascade",
          "Activity"=>"control",
          "Meeting"=>"control",
          "Milestone"=>"control",
          "Note"=>"cascade",
          "PeriodicMeeting"=>"control",
          "TestSession"=>"control",
          "Ticket"=>"control",
          "Link"=>"cascade"),
      "Contact"=>array("Affectation"=>"cascade"),
      "Document"=>array("DocumentVersion"=>"cascade"),
      "DocumentDirectory"=>array("Document"=>"control", "DocumentDirectory"=>"control"),
      // MTY - LEAVE SYSTEM
      "EmploymentContractEndReason"=>array("EmploymentContract"=>"control"),
      "EmploymentContractType"=>array(
          "EmploymentContract"=>"control",
          "CustomEarnedRulesOfEmploymentContractType"=>"cascade",
          "LeaveTypeOfEmploymentContractType"=>"cascade"),
      "LeaveType"=>array(
          "CustomEarnedRulesOfEmploymentContractType"=>"control",
          "EmployeeLeaveEarned"=>"control",
          "Leave"=>"control",
          "LeaveTypeOfEmploymentContractType"=>"control"),
      // MTY - LEAVE SYSTEM
      "Meeting"=>array("Assignment"=>"cascade"),
      // BEGIN - ADD BY TABARY - NOTIFICATION SYSTEM
      "Notifiable"=>array("NotificationDefinition"=>"confirm"),
      // END - ADD BY TABARY - NOTIFICATION SYSTEM
      "PeriodicMeeting"=>array("Meeting"=>"control"),
      "Product"=>array("Version"=>"control", "Requirement"=>"confirm", "TestCase"=>"confirm", "TestSession"=>"control"),
      "Project"=>array(
          "Action"=>"confirm",
          "Activity"=>"control",
          "Affectation"=>"cascade",
          "Baseline"=>"cascade",
          "CallForTender"=>"control",
          "Command"=>"control",
          "Document"=>"confirm",
          "Issue"=>"confirm",
          "IndicatorDefinitionPerProject"=>"cascade",
          "IndividualExpense"=>"confirm",
          "ProjectExpense"=>"confirm",
          "Term"=>"confirm",
          "Bill"=>"confirm",
          "Milestone"=>"confirm",
          "Project"=>"control",
          "Risk"=>"confirm",
          "Ticket"=>"control",
          "Decision"=>"confirm",
          "Meeting"=>"confirm",
          "Opportunity"=>"confirm",
          "PeriodicMeeting"=>"confirm",
          "ProviderBill"=>"control",
          "ProviderOrder"=>"control",
          "VersionProject"=>"cascade",
          "Question"=>"confirm",
          "Quotation"=>"confirm",
          "Requirement"=>"confirm",
          "StatusMailPerProject"=>"cascade",
          "Tender"=>"control",
          "TestCase"=>"confirm",
          "TestSession"=>"confirm",
          "TicketDelayPerProject"=>"cascade"),
      "Requirement"=>array("Requirement"=>"control"),
      "Resource"=>array(
          "Action"=>"control",
          "Activity"=>"control",
          "Affectation"=>"cascade",
          "Assignment"=>"cascade",
          "Issue"=>"control",
          "Milestone"=>"control",
          "Risk"=>"control",
          "Ticket"=>"control",
          "Decision"=>"control",
          "Meeting"=>"control",
          "Question"=>"control",
          "Requirement"=>"control",
          "ResourceTeamAffectation"=>"cascade",
          "TestCase"=>"control",
          "TestSession"=>"control"),
      "ResourceTeam"=>array("Assignment"=>"cascade", "Affectation"=>"cascade", "ResourceTeamAffectation"=>"cascade"),
      "TestCase"=>array("TestCase"=>"confirm", "TestCaseRun"=>"cascade"),
      "TestSession"=>array("TestCaseRun"=>"cascade", "Assignment"=>"cascade"),
      "User"=>array("Affectation"=>"cascade"),
      "Version"=>array("VersionProject"=>"cascade", "TestSession"=>"confirm"));

  public static $_cancelRecursiveControl=false;

  // ELIOTT - LEAVE SYSTEM
  private static $_classesArrayToBypassPHPCompatibilityIf=array(
      0=>"EmployeeLeaveEarned",
      1=>"LeaveTypeOfEmploymentContractType",
      2=>"CustomEarnedRulesOfEmploymentContractType");

  private static $_attributesArrayToBypassPHPCompatibilityIf=array(
      0=>"quantity",
      1=>"leftQuantity",
      2=>"oldLeftQuantity",
      3=>"leftQuantityBeforeClose");

  // ELIOTT - LEAVE SYSTEM
  /**
   * =========================================================================
   * Constructor.
   * Protected because this class must be extended.
   *
   * @param $id Int
   *          the id of the object in the database (null if not stored yet)
   * @return void
   */
  protected function __construct($id=NULL, $withoutDependentObjects=false) {
    if ($id=='undefined') $id=null;
    if (pq_trim($id) and !is_numeric($id)) {
      $class=get_class($this);
      traceHack("SqlElement->_construct : id '$id' is not numeric for class $class");
      return;
    }
    $this->id=$id;
    if ($this->id=='') {
      $this->id=null;
    }
    $this->getSqlElement($withoutDependentObjects);
  }

  /**
   * =========================================================================
   * Destructor
   *
   * @return void
   */
  protected function __destruct() {}

  // ============================================================================**********
  // UPDATE FUNCTIONS
  // ============================================================================**********

  /**
   * =========================================================================
   * Give public visibility to the saveSqlElement action
   *
   * @param
   *          force to avoid controls and force saving even if controls are false
   * @return message including definition of html hiddenfields to be used
   */
  public function save() {
    $startMicroTime=debugTraceUpdate("SqlElement::save()", $this, 'START', null);
    if ($this->id and pq_array_key_exists(get_class($this), self::$_cachedQuery)) {
      // PBER #11821 : be sure to clear the cache to read old value from DB.
      $whereClause='#id=' . $this->id;
      $class=get_class($this);
      if (pq_array_key_exists($whereClause, self::$_cachedQuery[$class])) unset(self::$_cachedQuery[$class][$whereClause]);
    }
    $peName=get_class($this) . 'PlanningElement';
    if (Parameter::getGlobalParameter('autoUpdateActivityStatus')=='YES' and property_exists($this, $peName)) {
      $old=$this->getOld();
    }
    $excludeConversion=(method_exists($this, 'getStaticExcludeConversion'))?$this->getStaticExcludeConversion():array();
    if ($this->hasCurrency()) {
      $conv=$this->getLocalToGlobalConversionRate();
      foreach ($this as $fld=>$val) {
        if (self::isAmount($fld) and !self::isLocal($fld) and property_exists($this, $fld . 'Local') and !in_array($fld, $excludeConversion)) {
          $locFld=$fld . 'Local';
          $newGLobalVal=floatval($this->calculateGlobalFromLocal($this->$locFld));
          if (abs(floatval($this->$fld)-$newGLobalVal)<1) { // Difference is small, check if difference is not just rounding
            $checkLocalValConv=round(floatval($this->calculateLocalFromGlobal($this->$fld)), 2);
            if ($checkLocalValConv==$this->$locFld) {
              $newGLobalVal=$this->$fld;
            }
          }
          $this->$fld=$newGLobalVal;
        }
      }
    }
    if (property_exists($this, 'idMilestone') and !isset($old)) {
      $old=$this->getOld();
    }
    if (property_exists($this, 'tags')) {
      if (!isset($old)) $old=$this->getOld();
      if ($this->tags and pq_substr($this->tags, 0, 1)!='#') $this->tags='#' . $this->tags;
      if ($this->tags and pq_substr($this->tags, -1)!='#') $this->tags=$this->tags . '#';
    }
    if (property_exists($this, 'idProject') and property_exists($this, 'idStatus') and !isset($old)) {
      $old=$this->getOld();
    }
    if (isset($this->_onlyCallSpecificSaveFunction) and $this->_onlyCallSpecificSaveFunction==true) return;
    $this->setAllDefaultValues(true);
    // PBER #8770 : define defaux sortOrder
    if (!$this->id and property_exists($this, 'sortOrder') and !$this->sortOrder and get_class($this)!='Project' and get_class($this)!='Organization') {
      $critArray=null;
      if (property_exists($this, 'refType') and property_exists($this, 'refId')) {
        $critArray=array('refType'=>$this->refType, 'refId'=>$this->refId);
      } else if (get_class($this)=='ActivityPrice') {
        $critArray=array('idProject'=>$this->idProject);
      } else if (get_class($this)=='Favorite' or get_class($this)=='FavoriteProjectList') {
        $critArray=array('idUser'=>$this->idUser);
      } else if (get_class($this)=='Filter') {
        $critArray=array('refType'=>$this->refType, 'idUser'=>$this->idUser);
      } else if (get_class($this)=='ChecklistDefinitionLine') {
        $critArray=array('idChecklistDefinition'=>$this->idChecklistDefinition);
      } else if (get_class($this)=='JobDefinition') {
        $critArray=array('idJoblistDefinition'=>$this->idJoblistDefinition);
      } else if (get_class($this)=='Layout' or get_class($this)=='ReportLayout') {
        $critArray=array('idUser'=>$this->idUser, 'objectClass'=>$this->objectClass);
      }
      if (substr(get_class($this), -4)=='Type' and property_exists($this, 'scope')) {
        $critArray['scope']=substr(get_class($this), 0, -4);
      }
      $last=$this->getMaxValueFromCriteria('sortOrder', $critArray);
      $next=intval($last)+10;
      $length=intval($this->getDataLength('sortOrder'));
      if (!$length or $length==0) $length=3;
      $max=intval(pq_substr('9999999999', 0, $length));
      if ($next>$max) $next=$max;
      $this->sortOrder=$next;
    }
    if (!property_exists($this, '_onlyCallSpecificSaveFunction') or !$this->_onlyCallSpecificSaveFunction) {
      // PlugIn Management
      $lstPluginEvt=Plugin::getEventScripts('beforeSave', get_class($this));
      foreach ($lstPluginEvt as $idScript=>$script) {
        require $script; // execute code
      }
    }
    if (property_exists($this, 'idProduct') and property_exists($this, 'idTargetProductVersion')) {
      if ($this->idTargetProductVersion and !$this->idProduct) {
        $getVersion=new Version($this->idTargetProductVersion, true);
        $this->idProduct=$getVersion->idProduct;
      }
    }
    if (property_exists($this, 'idMilestone') and Parameter::getGlobalParameter('milestoneFromVersion')=='YES' and ((property_exists($this, 'idTargetProductVersion') and $this->idTargetProductVersion) or (property_exists($this, 'idProductVersion') and $this->idProductVersion))) {
      $pv=new ProductVersion(((property_exists($this, 'idTargetProductVersion'))?$this->idTargetProductVersion:$this->idProductVersion), true);
      if ($pv->idMilestone) {
        $this->idMilestone=$pv->idMilestone;
      }
    }
    if (property_exists($this, '_SubTask')&&property_exists($this, 'idProject')) {
      if ($old->id!=null&&$old->idProject!=$this->idProject) {
        $listSubTask=SqlList::getListWithCrit('SubTask', array('refId'=>$this->id), 'id');
        foreach ($listSubTask as $idSubTask) {
          $sub=new SubTask($idSubTask);
          $sub->idProject=$this->idProject;
          $sub->save();
        }
      }
    }   
    if (get_class($this) != 'Dependency' and property_exists($this, 'idle') and !isset($old)) {          
      $old = $this->getOld();
    }
    $result=$this->saveSqlElement();
    if (getLastOperationStatus($result)=='OK' and property_exists($this, 'tags')) {
      // Save tag list is object tag
      $resultTag=Tag::saveTagList($this->tags, $old->tags, get_class($this), ((property_exists($this, 'idProject'))?$this->idProject:null));
      if ($resultTag!='' and getLastOperationStatus($resultTag)!='OK') {
        return $resultTag;
      }
    }  else if (getLastOperationStatus($result)=='ERROR') {
      if (pq_strpos(pq_strtolower($result),'deadlock')>0) {
        // PBER #9073 - Deadlock found : return explicit message
        $result=i18n('technicalError');
      }
    }
    if (getLastOperationStatus($result) == 'OK' and get_class($this)!='Dependency' and property_exists($this, 'idle') and $old->idle != $this->idle) {    
      Dependency::updateIdleForElement($this);
    }
    if (!property_exists($this, '_onlyCallSpecificSaveFunction') or !$this->_onlyCallSpecificSaveFunction) {
      // PlugIn Management
      $lstPluginEvt=Plugin::getEventScripts('afterSave', get_class($this));
      foreach ($lstPluginEvt as $idScript=>$script) {
        require $script; // execute code
      }
    }
    if (property_exists($this, 'idMilestone') and $this->idMilestone and $old->idMilestone!=$this->idMilestone) {
      $pe=SqlElement::getSingleSqlElementFromCriteria('MilestonePlanningElement', array(
          'refType'=>'Milestone',
          'refId'=>$this->idMilestone));
      if ($pe and $pe->id) {
        $pe->updateMilestonableItems(get_class($this), $this->id);
      }
    }
    // ticket #2822 - mehdi
    // $arrayStatusable("Project","Activity","Milestone","Meeting","TestSession");
    // $peName=get_class($this).'PlanningElement';
    if (Parameter::getGlobalParameter('autoUpdateActivityStatus')=='YES' and property_exists($this, $peName)) {
      $pe=$this->$peName;
      if (!$old->id or !$pe->topId or !property_exists($this, 'idStatus') or !property_exists($this, 'handled') or !property_exists($this, 'handledDate')) return $result;
      // $parentPe=new PlanningElement($pe->topId);
      $parentType=$pe->topRefType;
      $parent=new $parentType($pe->topRefId);
      if (!property_exists($parent, 'idStatus') or !property_exists($parent, 'handled') or !property_exists($parent, 'handledDate')) return $result;
      if ($this->handled and $this->handled!=$old->handled) {
        if (!$parent->handled) {
          $parent->handled=$this->handled;
          $parent->handledDate=date('Y-m-d');
          $allowedStatusList=Workflow::getAllowedStatusListForObject($parent);
          foreach ($allowedStatusList as $st) {
            if ($st->setHandledStatus) {
              $parent->idStatus=$st->id;
              $parent->save();
              break;
            }
          }
        }
      }
      $status=new Status($this->idStatus);
      $isStatHandled=($status->setHandledStatus)?true:false;
      $isStatDone=($status->setDoneStatus)?true:false;
      $isStatIdle=($status->setIdleStatus)?true:false;
      $isStatCancelled=($status->setCancelledStatus)?true:false;
      $isStatPaused=($status->setPausedStatus)?true:false;
      $status=new Status($old->idStatus);
      $isOldStatDone=($status->setDoneStatus)?true:false;
      $isOldStatIdle=($status->setIdleStatus)?true:false;
      $isOldStatCancelled=($status->setCancelledStatus)?true:false;
      $isOldStatPaused=($status->setPausedStatus)?true:false;
      SqlElement::$_cachedQuery['Status']=array();
      $st=new Status();
      $statusList=$st->getSqlElementsFromCriteria(null, null, null, null, true);
      if (($isStatDone and $isStatDone!=$isOldStatDone) or ($isStatIdle and $isStatIdle!=$isOldStatIdle) or ($isStatCancelled and $isStatCancelled!=$isOldStatCancelled)) {
        $allDone=true;
        $allIdle=true;
        $allCancelled=true;
        $peobj=new PlanningElement();
        $sons=$peobj->getSqlElementsFromCriteria(null, null, "topId=$pe->topId");
        foreach ($sons as $sonPe) {
          $sonType=$sonPe->refType;
          $son=new $sonType($sonPe->refId, true);
          // Change : only base on Status...
          if (!property_exists($son, 'idStatus') or !$son->idStatus) continue;
          if (!isset($statusList['#' . $son->idStatus])) continue;
          $sonStatus=$statusList['#' . $son->idStatus];
          if (!$sonStatus->setDoneStatus and !$sonStatus->setCancelledStatus) $allDone=false;
          if (!$sonStatus->setIdleStatus and !$sonStatus->setCancelledStatus) $allIdle=false;
          if (!$sonStatus->setCancelledStatus) $allCancelled=false;
          // if (! property_exists($son,'done') or ! property_exists($son,'idle') or ! property_exists($son,'cancelled')) continue;
          // if (!$son->done and !$son->cancelled) $allDone=false;
          // if (!$son->idle and !$son->cancelled) $allIdle=false;
          // if (!$son->cancelled) $allCancelled=false;
        }
        $setToDone=($isStatDone and $isStatDone!=$isOldStatDone and $allDone)?true:false;
        $setToIdle=($isStatIdle and $isStatIdle!=$isOldStatIdle and $allIdle)?true:false;
        $setToCancelled=($isStatCancelled and $isStatCancelled!=$isOldStatCancelled and $allCancelled)?true:false;
        if ($setToDone or $setToIdle or $setToCancelled) {
          $currentParentStatus=new Status($parent->idStatus);
          if ((!$setToDone or ($setToDone and $currentParentStatus->setDoneStatus)) and (!$setToIdle or ($setToIdle and $currentParentStatus->setIdleStatus)) and (!$setToCancelled or ($setToCancelled and $currentParentStatus->setCancelledStatus))) {
            // Nothing to do, already in a status corresponding to target
          } else {
            $allowedStatusList=Workflow::getAllowedStatusListForObject($parent);
            $saveParent=false;
            foreach ($allowedStatusList as $st) {
              if ($setToDone and $st->setDoneStatus and property_exists($parent, 'done') and property_exists($parent, 'doneDate')) {
                $parent->idStatus=$st->id;
                $parent->done=$this->done;
                $parent->doneDate=date('Y-m-d');
                $saveParent=true;
                $setToDone=false;
              }
              if ($setToIdle and $st->setIdleStatus and property_exists($parent, 'idle') and property_exists($parent, 'idleDate')) {
                $parent->idStatus=$st->id;
                $parent->idle=$this->idle;
                $parent->idleDate=date('Y-m-d');
                $saveParent=true;
                $setToIdle=false;
              }
              if ($setToCancelled and $st->setCancelledStatus and property_exists($parent, 'cancelled')) {
                $parent->idStatus=$st->id;
                $parent->cancelled=$this->cancelled;
                // $parent->doneDate=date('Y-m-d');
                $saveParent=true;
                $setToCancelled=false;
              }
            }
            if ($saveParent) {
              $resParent=$parent->save();
            }
          }
        }
      }
    }
    if (get_class($this)=='Ticket') {
      $now=pq_strtotime("now");
      if ($this->handled and !$this->done and !$this->idle and !$this->paused) {
        $statPeriod=new StatusPeriod();
        $statPeriodList=$statPeriod->getSqlElementsFromCriteria(array('refType'=>get_class($this), 'refId'=>$this->id), null, null, 'id DESC');
        if (count($statPeriodList)>0) {
          $statPeriod=$statPeriodList[0];
        }
        if ($statPeriod->id and $statPeriod->active==0) {
          $statPeriod->endDate=date('Y-m-d H:i:s');
          $statPeriod->idStatusEnd=$this->idStatus;
          $statPeriod->idUserEnd=getSessionUser()->id;
          $startDate=new DateTime($statPeriod->startDate);
          $endDate=new DateTime(date('Y-m-d H:i:s'));
          $duration=$startDate->diff($endDate, true);
          $start=pq_substr($statPeriod->startDate, 0, 16) . ':00';
          $end=date('Y-m-d H:i') . ':00';
          $statPeriod->duration=abs(pq_strtotime($start)-pq_strtotime($end));
          $durationOpDay=openHourDiffTime($statPeriod->startDate, date('Y-m-d H:i:s'), $this->idProject);
          $statPeriod->durationOpenTime=$durationOpDay;
          $statPeriod->save();
        }
        $tz=Parameter::getGlobalParameter('paramDefaultTimezone');
        if ($tz) date_default_timezone_set($tz);
        else date_default_timezone_set('Europe/Paris');
        if ($statPeriod->active==0) {
          $newStatPeriod=new StatusPeriod();
          $newStatPeriod->refId=$this->id;
          $newStatPeriod->refType=get_class($this);
          $newStatPeriod->active=1;
          $newStatPeriod->startDate=date('Y-m-d H:i:s', pq_strtotime('now'));
          $newStatPeriod->type='handled';
          $newStatPeriod->idStatusStart=$this->idStatus;
          $newStatPeriod->idUserStart=getSessionUser()->id;
          $newStatPeriod->save();
        }
      } else {
        $statPeriod=new StatusPeriod();
        $statPeriodList=$statPeriod->getSqlElementsFromCriteria(array('refType'=>get_class($this), 'refId'=>$this->id), null, null, 'id DESC');
        if (count($statPeriodList)>0) {
          $statPeriod=$statPeriodList[0];
        }
        $type='recorded';
        if ($this->idle) {
          $type='idle';
        } else if ($this->done) {
          $type='done';
        } else if ($this->paused) {
          $type='inPaused';
        } else if ($this->handled) {
          $type='handled';
        }
        if ($statPeriod->id and $statPeriod->active==1) {
          $statPeriod->endDate=date('Y-m-d H:i:s');
          $statPeriod->idStatusEnd=$this->idStatus;
          $statPeriod->idUserEnd=getSessionUser()->id;
          $start=pq_substr($statPeriod->startDate, 0, 16) . ':00';
          $end=date('Y-m-d H:i') . ':00';
          $statPeriod->duration=abs(pq_strtotime($start)-pq_strtotime($end));
          $durationOpDay=openHourDiffTime($statPeriod->startDate, date('Y-m-d H:i:s'), $this->idProject);
          $statPeriod->durationOpenTime=$durationOpDay;
          $statPeriod->save();
        }
        $tz=Parameter::getGlobalParameter('paramDefaultTimezone');
        if ($tz) date_default_timezone_set($tz);
        else date_default_timezone_set('Europe/Paris');
        if ($statPeriod->active==1) {
          $newStatPeriod=new StatusPeriod();
          $newStatPeriod->refId=$this->id;
          $newStatPeriod->refType=get_class($this);
          $newStatPeriod->active=0;
          $newStatPeriod->startDate=date('Y-m-d H:i:s', pq_strtotime('now'));
          $newStatPeriod->type=$type;
          $newStatPeriod->idStatusStart=$this->idStatus;
          $newStatPeriod->idUserStart=getSessionUser()->id;
          $newStatPeriod->save();
        }
      }
    }
    // Synchronization
    if (getLastOperationStatus($result)=='OK' and property_exists($this, 'idProject') and property_exists($this, 'idStatus')) {
      // Start Synchronization on status change or on project change
      $syncDone=false;
      if (Synchronization::isProjectSynchronized($this->idProject) and ($old->idStatus!=$this->idStatus or $old->idProject!=$this->idProject)) {
        $sync=Synchronization::getProjectSynchronizationDefinition($this->idProject);
        if ($sync->idStatus==$this->idStatus and $sync->originType==get_class($this)) {
          $typeName=$this->getObjectTypeName();
          if (!$sync->idOrigineType or (property_exists($this, $typeName) and $this->$typeName==$sync->idOrigineType)) {
            $resSync=$sync->startSynchronization($this);
            if (!$resSync) {
              $result=Synchronization::getLastErrorMessage();
            } else {
              $syncDone=true;
            }
          }
        }
      }
      // Execute synchronization if object is synchronized
      if (SynchronizedItems::getSynchronizedItemKey(get_class($this), $this->id)!=null) {
        $resSync=Synchronization::synchronizeFields($this, $old);
        if (getLastOperationStatus($resSync)!='OK' and getLastOperationStatus($resSync)!='NO_CHANGE') {
          $result=$resSync;
        }
      }
    }
    debugTraceUpdate("SqlElement::save()", $this, 'END', $startMicroTime);
    return $result;
  }

  public function insert() { // Specific function to force insert with a defined id - Reserved to Import fonction
    $this->_onlyCallSpecificSaveFunction=true;
    // PlugIn Management
    $lstPluginEvt=Plugin::getEventScripts('beforeSave', get_class($this));
    foreach ($lstPluginEvt as $idScript=>$script) {
      require $script; // execute code
    }
    $this->save(); // To force the update of fields calculated in the save function ...
    $this->_onlyCallSpecificSaveFunction=false;
    $result=$this->saveSqlElement(false, false, true);
    // PlugIn Management
    $lstPluginEvt=Plugin::getEventScripts('afterSave', get_class($this));
    foreach ($lstPluginEvt as $idScript=>$script) {
      require $script; // execute code
    }
    return $result;
  }

  public function saveForced($withoutDependencies=false) {
    // PlugIn Management
    $lstPluginEvt=Plugin::getEventScripts('beforeSave', get_class($this));
    foreach ($lstPluginEvt as $idScript=>$script) {
      require $script; // execute code
    }
    $result=$this->saveSqlElement(true, $withoutDependencies);
    // PlugIn Management
    $lstPluginEvt=Plugin::getEventScripts('afterSave', get_class($this));
    foreach ($lstPluginEvt as $idScript=>$script) {
      require $script; // execute code
    }
    return $result;
  }

  // Save without controls and without extra save() feature defined in local save() method (for corresponding class)
  public function simpleSave($withoutDependencies=false) {
    $startMicroTime=debugTraceUpdate("SqlElement::simpleSave()", $this, 'START', null);
    $result=$this->saveForced($withoutDependencies);
    debugTraceUpdate("SqlElement::simpleSave()", $this, 'END', $startMicroTime);
    return $result;
  }

  /**
   * =========================================================================
   * Give public visibility to the purgeSqlElement action
   *
   * @return message including definition of html hiddenfields to be used
   */
  public function purge($clause) {
    return $this->purgeSqlElement($clause);
  }

  /**
   * =========================================================================
   * Give public visibility to the closeSqlElement action
   *
   * @return message including definition of html hiddenfields to be used
   */
  public function close($clause) {
    return $this->closeSqlElement($clause);
  }

  /**
   * =========================================================================
   * Give public visibility to the deleteSqlElement action
   *
   * @return message including definition of html hiddenfields to be used
   */
  public function delete() {
    global $debugTraceUpdates, $debugTraceHistory;
    $keyObj=get_class($this) . '#' . $this->id;
    if (isset(self::$_deletedObject[$keyObj])) return; // already deleted, avoid recursive infinite loop
    self::$_deletedObject[$keyObj]=$keyObj;
    // PlugIn Management
    if (isset($debugTraceUpdates) and $debugTraceUpdates==true) {
      if (!property_exists($this, '_noHistory') or (isset($debugTraceHistory) and $debugTraceHistory==true)) debugTraceLog("Start DELETE for " . get_class($this) . " #" . $this->id);
      $startMicroTime=microtime(true);
    }
    $list=Plugin::getEventScripts('beforeDelete', get_class($this));
    foreach ($list as $idScript=>$script) {
      require $script; // execute code
    }
    $result=$this->deleteSqlElement();
    // PlugIn Management
    $list=Plugin::getEventScripts('afterDelete', get_class($this));
    foreach ($list as $idScript=>$script) {
      require $script; // execute code
    }
    if (isset($debugTraceUpdates) and $debugTraceUpdates==true) {
      if (!property_exists($this, '_noHistory') or (isset($debugTraceHistory) and $debugTraceHistory==true)) debugTraceLog("End DELETE for " . get_class($this) . " #" . $this->id . " => " . round((microtime(true)-$startMicroTime)*1000000)/1000000);
    }
    if (getLastOperationStatus($result)=='OK' and property_exists($this, 'idProject') and property_exists($this, 'idStatus')) {
      if (SynchronizedItems::getSynchronizedItemKey(get_class($this), $this->id)!=null) {
        // Delete existing synchonizedItems when one of then is deleted
        SynchronizedItems::deletedSynchronizedItem(get_class($this), $this->id);
      }
    }
    if (getLastOperationStatus($result)=='ERROR') {
      if (pq_strpos(pq_strtolower($result),'deadlock')>0) {
        // PBER #9073 - Deadlock found : return explicit message
        $result=i18n('technicalError');
      }
    }
    return $result;
  }

  /**
   * =========================================================================
   * Give public visibility to the copySqlElement action
   *
   * @return Object the new object
   */
  public function copy() {
    global $debugTraceUpdates, $debugTraceHistory;
    if (isset($debugTraceUpdates) and $debugTraceUpdates==true) {
      if (!property_exists($this, '_noHistory') or (isset($debugTraceHistory) and $debugTraceHistory==true)) debugTraceLog("Start COPY for " . get_class($this) . " #" . $this->id);
      $startMicroTime=microtime(true);
    }
    self::setCopyInProgress();
    $result=$this->copySqlElement();
    if (isset($debugTraceUpdates) and $debugTraceUpdates==true) {
      if (!property_exists($this, '_noHistory') or (isset($debugTraceHistory) and $debugTraceHistory==true)) debugTraceLog("End COPY for " . get_class($this) . " #" . $this->id . " => " . round((microtime(true)-$startMicroTime)*1000000)/1000000);
    }
    return $result;
  }

  public function copyTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments=false, $withAffectations=false, $toProject=null, $toActivity=null, $copyToWithResult=false, $copyToWithActivityPrice=false, $copyToWithStatus=false, $copyToWithSubTask=false, $moveAfterCreate=null) {
    global $debugTraceUpdates, $debugTraceHistory;
    scriptLog("SqlElement::copyTo(newClass=$newClass, newType=$newType, newName=$newName, newProject=$newProject, setOrigin=$setOrigin, withNotes=$withNotes, withAttachments=$withAttachments, withLinks=$withLinks, withAssignments=$withAssignments, withAffectations=$withAffectations, toProject=$toProject, toActivity=$toActivity, copyToWithResult=$copyToWithResult, copyToWithStatus=$copyToWithStatus, copyToWithSubTask=$copyToWithSubTask, moveAfterCreate = $moveAfterCreate)");
    scriptLog(" for " . debugDisplayObj($this));
    if (isset($debugTraceUpdates) and $debugTraceUpdates==true) {
      if (!property_exists($this, '_noHistory') or (isset($debugTraceHistory) and $debugTraceHistory==true)) debugTraceLog("Start COPYTO for " . get_class($this) . " #" . $this->id);
      $startMicroTime=microtime(true);
    }
    self::setCopyInProgress();
    $result=$this->copySqlElementTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments, $withAffectations, $toProject, $toActivity, $copyToWithResult, $copyToWithStatus, $copyToWithSubTask, $moveAfterCreate);
    if (isset($debugTraceUpdates) and $debugTraceUpdates==true) {
      if (!property_exists($this, '_noHistory') or (isset($debugTraceHistory) and $debugTraceHistory==true)) debugTraceLog("End COPYTO for " . get_class($this) . " #" . $this->id . " => " . round((microtime(true)-$startMicroTime)*1000000)/1000000);
    }
    return $result;
  }

  public static function setCopyInProgress() {
    self::$_copyInProgress=true;
  }

  public static function isCopyInProgress() {
    if (isset(self::$_copyInProgress) and self::$_copyInProgress==true) {
      return true;
    } else {
      return false;
    }
  }

  // Fill required fields (for instance on copy, transform prospects)
  // Will set values for fields that are lists
  public function fillRequiredFields() {
    foreach ($this as $fld=>$val) {
      if (pq_substr($fld, 0, 1=='_')) continue;
      if (!$val and isForeignKey($fld, $this) and $this->isAttributeSetToField($fld, 'required')) {
        $colWithoutAlias=foreignKeyWithoutAlias($fld);
        $cls=pq_substr($colWithoutAlias, 2);
        $list=SqlList::getList($cls, 'id');
        $default=reset($list);
        $this->$fld=$default;
      }
    }
  }

  /**
   * =========================================================================
   * Save an object to the database
   *
   * @return void
   */
  private function saveSqlElement($force=false, $withoutDependencies=false, $forceInsert=false) {
    // traceLog("saveSqlElement(" . get_class($this) . "#$this->id)"
    // . ((SqlElement::is_subclass_of($this,'PlanningElement'))?" => $this->refType #$this->refId":''));
    // if (get_class($this)=='History') traceLog(" => $this->colName : '$this->oldValue'->'$this->newValue'");
    // #305
    self::$_cachedQuery['Type']=array();
    self::$_cachedQuery[SqlElement::getTypeClassName(get_class($this))]=array();
    self::$_cachedQuery['Status']=array();
    self::$_cachedQuery['PlanningMode']=array();
    self::$_cachedQuery[get_class($this) . 'PlanningMode']=array();

    $this->recalculateCheckboxes();
    // select operation to be executed
    if ($force or self::$_skipAllControls) {
      $control="OK";
    } else {
      $control=$this->control();
      $class=get_class($this);
      if (($control=='OK' or pq_strpos($control, 'id="confirmControl" value="save"')>0) and property_exists($class, $class . 'PlanningElement')) {
        $pe=$class . 'PlanningElement';
        $controlPe=$this->$pe->control();
        if ($controlPe!='OK') {
          $control=$controlPe;
        }
      }
      if (($control=='OK' or pq_strpos($control, 'id="confirmControl" value="save"')>0) and property_exists($this, 'WorkElement') and isset($this->WorkElement)) {
        $we='WorkElement';
        $controlWe=$this->WorkElement->control();
        if ($controlWe!='OK') {
          $control=$controlWe;
        }
      }
      if (($control=='OK' or pq_strpos($control, 'id="confirmControl" value="save"')>0) and property_exists($class, 'OrganizationBudgetElementCurrent') and Module::isModuleActive('moduleBudgetFunctionOfOrga')) {
        // Parameter::getGlobalParameter ( 'useOrganizationBudgetElement' ) === "YES"
        // ADD BY TABARY Marc - 2017-06-06 - USE OR NOT ORGANIZATION BUDGETELEMENT
        $be='OrganizationBudgetElementCurrent';
        $controlBe=$this->$be->control();
        if ($controlBe!='OK') {
          $control=$controlBe;
        }
      }
    }
    if ($control=="OK") {
      // $old=new Project();
      if (property_exists($this, 'idStatus') or property_exists($this, 'reference') or property_exists($this, 'idResource') or property_exists($this, 'description') or property_exists($this, 'result')) {
        $class=get_class($this);
        $old=new $class($this->id, true);
      }
      $statusChanged=false;
      $responsibleChanged=false;
      $descriptionChange=false;
      $resultChange=false;
      if (property_exists($this, 'reference') and isset($old)) {
        $this->setReference(false, $old);
      }
      if (property_exists($this, 'idResource') and !pq_trim($this->idResource) and !SqlElement::isCopyInProgress()) {
        $this->setDefaultResponsible();
      }
      if (!$this->id and $this instanceof PlanningElement) { // For planning element , check that not existing yet
        $critPe=array('refType'=>$this->refType, 'refId'=>$this->refId);
        $pe=SqlElement::getSingleSqlElementFromCriteria('PlanningElement', $critPe);
        if ($pe->id) {
          $this->id=$pe->id;
        }
      }
      if ($this->id!=null and !$forceInsert) {
        if (property_exists($this, 'idStatus')) {
          if ($this->idStatus and isset($old)) {
            if ($old->idStatus!=$this->idStatus) {
              $statusChanged=true;
            }
          }
        }
        $newItem=false;
        $returnValue=$this->updateSqlElement($force, $withoutDependencies);
      } else {
        if (property_exists($this, 'idStatus')) {
          $statusChanged=true;
        }
        $newItem=true;
        $returnValue=$this->insertSqlElement($forceInsert);
      }
      if (property_exists($this, 'idResource') and !$newItem and isset($old)) {
        if (pq_trim($this->idResource) and pq_trim($this->idResource)!=pq_trim($old->idResource)) {
          $responsibleChanged=true;
        }
      }
      if (property_exists($this, 'description') and !$newItem and isset($old)) {
        if (pq_trim($this->description)!=pq_trim($old->description)) {
          $descriptionChange=true;
        }
      }
      if (property_exists($this, 'result') and !$newItem and isset($old)) {
        if ($this->result!=$old->result) {
          $resultChange=true;
        }
      }

      $hasPriorityChanged=false;
      if (property_exists($this, 'idPriority') and isset($old) and $old->id and property_exists($old, 'idPriority') and $this->idPriority!=$old->idPriority) $hasPriorityChanged=true;
      $hasUserBeenCreated=false;
      if ((get_class($this)=="User"&&$old->id=="") or ((get_class($this)=="Resource" or get_class($this)=="Contact") and $this->isUser and !$old->isUser)) $hasUserBeenCreated=true;
      // if (($statusChanged or $responsibleChanged) and pq_stripos($returnValue,'id="lastOperationStatus" value="OK"')>0 ) {

      if (pq_stripos($returnValue, 'id="lastOperationStatus" value="OK"')>0 and !property_exists($this, '_noHistory') and !SqlElement::is_a($this, 'PlanningElement')) {
        $mailResult=$this->sendMailIfMailable($newItem, $statusChanged, false, $responsibleChanged, false, false, false, $descriptionChange, $resultChange, false, false, true, false, false, false, false, false, $hasPriorityChanged, $hasUserBeenCreated);
        // $this->sendAlertNotification($newItem, $statusChanged, false, $responsibleChanged, false, false, false, $descriptionChange, $resultChange, false, false, true,false,false, false, false, false, $hasPriorityChanged, $hasUserBeenCreated);
        if ($mailResult) {
          $returnValue=pq_str_replace('${mailMsg}', ' - ' . Mail::getResultMessage($mailResult), $returnValue);
        } else {
          $returnValue=pq_str_replace('${mailMsg}', '', $returnValue);
        }
      } else {
        $returnValue=pq_str_replace('${mailMsg}', '', $returnValue);
      }
      // indicators
      $classIndicatorable=(SqlElement::is_a($this, 'PlanningElement'))?$this->refType:get_class($this);
      global $doNotTriggerAlerts;
      if (SqlList::getIdFromTranslatableName('Indicatorable', $classIndicatorable) and !$doNotTriggerAlerts) {
        $indDef=new IndicatorDefinition();
        if (property_exists($this, 'idProject')) {
          $idP=(get_class($this)=='Project')?$this->id:$this->idProject;
          $proj=new Project($idP, true);
          $listProj=$proj->getTopProjectList(true);
          $listProj=implode(',', $listProj);
          if (pq_trim($listProj)=='') $listProj='0';
          // $crit = array('nameIndicatorable' => get_class ( $this ), 'idle' => '0','idProject' => $idP);
          $where="nameIndicatorable='$classIndicatorable' and idle = 0 and idProject in (" . $listProj . ")";
        } else {
          // $crit = array('nameIndicatorable' => get_class ( $this ), 'idle' => '0');
          $where="nameIndicatorable='$classIndicatorable' and idle = 0";
        }
        $lstInd=$indDef->getSqlElementsFromCriteria(null, false, $where);
        if (!$lstInd or count($lstInd)==0) {
          $crit=array('nameIndicatorable'=>$classIndicatorable, 'idle'=>'0', 'idProject'=>"");
          $lstInd=$indDef->getSqlElementsFromCriteria($crit, false);
        }
        $fldVal='';
        foreach ($lstInd as $ind) {
          // $fldType = 'id' . (($classIndicatorable == 'TicketSimple') ? 'Ticket' : $classIndicatorable) . 'Type';
          $fldType=self::getTypeName($classIndicatorable);
          if (SqlElement::is_a($this, 'PlanningElement')) {
            $objType=new $classIndicatorable($this->refId);
            if (property_exists($objType, $fldType)) $fldVal=$objType->$fldType;
          } else {
            $objType=$this;
            if (property_exists($objType, $fldType)) $fldVal=$this->$fldType;
          }
          if (!$ind->idType or $ind->idType==$fldVal) {
            IndicatorValue::addIndicatorValue($ind, $objType);
          }
        }
      }
      if (property_exists($this, 'idle') and $this->idle) {
        $this->dispatchClose();
      }
      return $returnValue;
    } else {
      // errors on control => don't save, display error message
      if (pq_strpos($control, 'id="confirmControl" value="save"')>0) {
        $returnValue='<b>' . i18n('messageConfirmationNeeded') . '</b><br/>' . $control;
        $returnValue.='<input type="hidden" id="lastOperationStatus" value="CONFIRM" />';
      } else {
        $returnValue='<b>' . i18n('messageInvalidControls') . '</b><br/>' . $control;
        $returnValue.='<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      }
      $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
      $returnValue.='<input type="hidden" id="lastOperation" value="control" />';
      return $returnValue;
    }
  }

  private function dispatchClose() {
    global $mode;
    if (property_exists($this, 'idle') and $this->idle) {
      $relationShip=self::$_closeRelationShip;
      $user=getSessionUser();
      $crit=array('idProfile'=>$user->getProfile($this), 'scope'=>'canForceClose');
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
      $canForceClose=false;
      if ($habil and $habil->id and $habil->rightAccess=='1') {
        $canForceClose=true;
      }
      if (pq_array_key_exists(get_class($this), $relationShip)) {
        $objects='';
        $error=false;
        foreach ($relationShip[get_class($this)] as $object=>$mode) {
          if ($canForceClose and $mode=='control') {
            $mode="confirm";
          }
          if (($mode=='cascade' or $mode=='confirm') and property_exists($object, 'idle')) {
            $where=null;
            $obj=new $object();
            $crit=array('id' . get_class($this)=>$this->id, 'idle'=>'0');
            if (property_exists($obj, 'refType') and property_exists($obj, 'refId')) {
              if (property_exists($obj, 'id' . get_class($this))) {
                $crit=null;
                $where="(id" . get_class($this) . "=" . $this->id . " or (refType='" . get_class($this) . "' and refId=" . $this->id . ")) and idle=0";
              } else {
                $crit=array("refType"=>get_class($this), "refId"=>$this->id, "idle"=>'0');
              }
            }
            if ($object=="Dependency") {
              $crit=null;
              $where="idle=0 and ((predecessorRefType='" . get_class($this) . "' and predecessorRefId=" . $this->id . ")" . " or (successorRefType='" . get_class($this) . "' and successorRefId=" . $this->id . "))";
            }
            if ($object=="Link") {
              $crit=null;
              $where="idle=0 and ((ref1Type='" . get_class($this) . "' and ref1Id=" . Sql::fmtId($this->id) . ")" . " or (ref2Type='" . get_class($this) . "' and ref2Id=" . Sql::fmtId($this->id) . "))";
            }
            if (get_class($this)=='ResourceTeam' and $object!='ResourceTeamAffectation') {
              $crit=array('idResource'=>$this->id);
            }
            $list=$obj->getSqlElementsFromCriteria($crit, false, $where);
            foreach ($list as $o) {
              $o->idle=1;
              if (property_exists($o, 'idleDate') and !pq_trim($o->idleDate)) {
                $o->idleDate=date('Y-m-d');
              }
              if (property_exists($o, 'idleDateTime') and !pq_trim($o->idleDateTime)) {
                $o->idleDateTime=date('Y-m-d H:i:s');
              }
              self::$_skipAllControls="checkboxes";
              $resO=$o->save();
              self::$_skipAllControls=false;
            }
          }
        }
        if ($objects!="") {
          if ($error) {
            $result.="<br/>" . i18n("errorControlClose") . $objects;
          } else {
            $result.='<input type="hidden" id="confirmControl" value="save" /><br/>' . i18n("confirmControlSave") . $objects;
          }
        }
      }
    }
  }

  /**
   * =========================================================================
   * Save an object to the database : new object
   *
   * @return void
   */
  private function insertSqlElement($forceInsert=false) {
    if (get_class($this)=='Origin') {
      if (!$this->originId or !$this->originType) {
        return;
      }
    }
    $depedantObjects=array();
    $returnStatus="OK";
    $objectClass=get_class($this);
    $query="insert into " . $this->getDatabaseTableName();
    $queryColumns="";
    $queryValues="";
    // initialize object definition criteria
    $databaseCriteriaList=$this->getDatabaseCriteria();
    foreach ($databaseCriteriaList as $col_name=>$col_value) {
      $dataType=$this->getDataType($col_name);
      $dataLength=$this->getDataLength($col_name);
      $attribute=$this->getFieldAttributes($col_name);
      if (pq_strpos($attribute, 'calculated')===false) {
        if ($dataType=='int' and $dataLength==1) {
          if ($col_value==NULL or $col_value=="") {
            $col_value='0';
          }
        }
        if ($dataType=='decimal') {
          $col_value=pq_str_replace(',', '.', $col_value);
        }
        if ($col_value!=NULL and $col_value!='' and $col_value!=' ' and ($col_name!='id' or $forceInsert)) {
          if ($queryColumns!="") {
            $queryColumns.=", ";
            $queryValues.=", ";
          }
          $queryColumns.=$this->getDatabaseColumnName($col_name);
          $queryValues.=Sql::str($col_value, $objectClass);
        }
      }
    }
    if (Sql::isPgsql()) {
      $queryColumns=pq_strtolower($queryColumns);
    }
    if (property_exists($this, 'lastUpdateDateTime') and !SqlElement::$_doNotSaveLastUpdateDateTime) { // Initialize lastUpdateDateTime (for tickets)
      $this->lastUpdateDateTime=date('Y-m-d H:i:s');
    }
    // get all data
    foreach ($this as $col_name=>$col_value) {
      $attribute=$this->getFieldAttributes($col_name);
      if (pq_strpos($attribute, 'calculated')===false) {
        if (pq_substr($col_name, 0, 1)=="_") {
          // not a fiels, just for presentation purpose
        } else if (pq_ucfirst($col_name)==$col_name) {
          // if property is an object, store it to save it at the end of script
          $depedantObjects[$col_name]=($this->$col_name);
        } else if (pq_array_key_exists($col_name, $databaseCriteriaList)) {
          // Do not overwrite the default value from databaseCriteria, and do not double-set in insert clause
        } else {
          $dataType=$this->getDataType($col_name);
          $dataLength=$this->getDataLength($col_name);
          if ($dataType=='int' and $dataLength==1) {
            if ($col_value==NULL or $col_value=="") {
              $col_value='0';
            }else{
              $col_value = intval($col_value);
            }
          }
          if ($dataLength>4000 and getEditorType()=='text') {
            $col_value=nl2brForPlainText($col_value);
          }
          if ($col_value!=NULL and $col_value!='' and $col_value!=' ' and ($col_name!='id' or $forceInsert) and pq_strpos($queryColumns, ' ' . $this->getDatabaseColumnName($col_name) . ' ')===false) {
            if ($queryColumns!="") {
              $queryColumns.=",";
              $queryValues.=", ";
            }
            $queryColumns.=' ' . $this->getDatabaseColumnName($col_name) . ' ';
            $queryValues.=Sql::str($col_value, $objectClass);
          }
        }
      }
    }
    $query.=" ($queryColumns) values ($queryValues)";
    // execute request
    $result=Sql::query($query);
    if (!$result) {
      $returnStatus="ERROR";
    }
    // save history
    $newId=Sql::$lastQueryNewid;
    $this->id=$newId;
    if ($returnStatus!="ERROR" and !property_exists($this, '_noHistory')) {
      if (get_class($this)=='SubTask') {
        $result=History::store($this, $objectClass, $this->id, 'insert', get_class($this), '', $this->name);
      } else {
        $result=History::store($this, $objectClass, $newId, 'insert');
      }
      if (!$result) {
        $returnStatus="ERROR";
      }
    }
    // save depedant elements (properties that are objects)
    if ($returnStatus!="ERROR" and $returnStatus!="INVALID") {
      $returnStatus=$this->saveDependantObjects($depedantObjects, $returnStatus);
      if ($returnStatus=="ERROR") {
        $returnValue=Sql::$lastQueryErrorMessage;
      } else if ($returnStatus=="OK") {
        $returnValue=i18n(get_class($this)) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultUpdated');
      } else if ($returnStatus=="NO_CHANGE" or $returnStatus=="INCOMPLETE" or $returnStatus=="WARNING" or $returnStatus=="CONFIRM") {
        // OK
      } else if (getLastOperationStatus($returnStatus)=='INVALID') {
        return $returnStatus;
      }
    }
    // Prepare return data
    if ($returnStatus!="ERROR") {
      $returnValue=i18n(get_class($this)) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultInserted');
    } else {
      $returnValue=Sql::$lastQueryErrorMessage;
    }
    if ($returnStatus=="OK") {
      $returnValue.='${mailMsg}';
    }
    $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    $returnValue.='<input type="hidden" id="lastOperation" value="insert" />';
    $returnValue.='<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    return $returnValue;
  }

  /**
   * Get old values (stored in session) to :
   * 1) build the smallest query
   * 2) save change history
   *
   * @param string $objectClass
   * @param string $force
   * @return Object the currently accesses object
   */
  public static function getCurrentObject($objectClass=null, $objectId=null, $throwError=false, $force=false, $isComboDetail=false) {
    $oldObject=null;
    if ($force) {
      if ($objectClass) {
        return new $objectClass($objectId);
      } else {
        return null;
      }
    }
    if (sessionValueExists('currentObject' . (($isComboDetail)?'_comboDetail':''))) {
      $testObject=getSessionValue('currentObject' . (($isComboDetail)?'_comboDetail':''));
      if (!$objectClass or (get_class($testObject)==$objectClass and $testObject->id==$objectId)) {
        $oldObject=$testObject;
      } else if ($throwError) {
        throwError('currentObject (' . get_class($testObject) . ' #' . $testObject->id . ') is not of the expectec class (' . $objectClass . ')');
        return null;
      }
    }
    if (!$oldObject and $objectClass) {
      $oldObject=new $objectClass($objectId);
    }
    return $oldObject;
  }

  public static function setCurrentObject($obj, $isComboDetail=false) {
    $obj=self::setCurrentObjectTimestamp($obj);
    if ($isComboDetail) {
      setSessionValue('currentObject_comboDetail', $obj);
    } else {
      setSessionValue('currentObject', $obj);
    }
  }

  public static function setCurrentObjectTimestamp($obj) {
    if (!$obj or !is_object($obj)) return;
    $obj->_storageDateTime=date('Y-m-d H:i:s');
    return $obj;
  }

  public static function getCurrentObjectTimestamp($obj) {
    if (!$obj) $obj=self::getCurrentObject();
    if (!$obj or !is_object($obj)) return;
    return $obj->_storageDateTime;
  }

  public static function resetCurrentObjectTimestamp($obj=null) {
    if (!$obj) $obj=self::getCurrentObject();
    if (!$obj or !is_object($obj)) return;
    $obj->_storageDateTime=self::setCurrentObjectTimestamp($obj);
    self::setCurrentObject($obj);
    return $obj->_storageDateTime;
  }

  public static function unsetCurrentObject() {
    if (sessionValueExists('currentObject')) {
      unsetSessionValue('currentObject');
    }
  }

  /**
   * =========================================================================
   * save an object to the database : existing object
   *
   * @return void
   */
  private function updateSqlElement($force=false, $withoutDependencies=false) {
    // traceLog('updateSqlElement (for ' . get_class($this) . ' #' . $this->id . ')');
    $returnValue=i18n('messageNoChange') . ' ' . i18n(get_class($this)) . ' #' . $this->id;
    $returnStatus='NO_CHANGE';
    $depedantObjects=array();
    $objectClass=get_class($this);
    $arrayCols=array();
    if (Sql::isPgsql()) $arrayCols['lastupdatedatetime']='$lastUpdateDateTime';
    else $arrayCols['lastUpdateDateTime']='$lastUpdateDateTime';
    $idleChange=false;
    $projectChange=false;
    // Get old values (stored) to : 1) build the smallest query 2) save change history
    $oldObject=self::getCurrentObject(get_class($this), $this->id, false, $force);
    // Specific treatment for other versions
    $versionTypes=array(
        'Version',
        'OriginalVersion',
        'OriginalProductVersion',
        'OriginalComponentVersion',
        'TargetVersion',
        'TargetProductVersion',
        'TargetComponentVersion');
    foreach ($versionTypes as $versType) { // If version is cleared and item has other version, replace main with first other
      $otherFld='_Other' . $versType;
      $versFld='id' . $versType;
      if (property_exists($this, $versFld) and property_exists($this, $otherFld)) {
        usort($oldObject->$otherFld, "OtherVersion::sort");
        foreach ($oldObject->$otherFld as $otherVers) {
          if (!pq_trim($this->$versFld)) {
            $this->$versFld=$otherVers->idVersion;
          }
          if ($otherVers->idVersion==$this->$versFld) {
            $otherVers->delete();
          }
        }
      }
    }
    if (property_exists($this, 'idClient') and property_exists($this, '_OtherClient')) { // If client is cleared and item has other client, replace main with first other
      usort($oldObject->_OtherClient, "OtherClient::sort");
      foreach ($oldObject->_OtherClient as $otherClient) {
        if (!pq_trim($this->idClient)) {
          $this->idClient=$otherClient->idClient;
        }
        if ($otherClient->idClient==$this->idClient) {
          $otherClient->delete();
        }
      }
    }
    $nbChanged=0;
    $query="update " . $this->getDatabaseTableName();
    // get all data, and identify if changes
    foreach ($this as $col_name=>$col_new_value) {
      $attribute=$this->getFieldAttributes($col_name);
      if (pq_strpos($attribute, 'calculated')!==false) {
        // calculated field, not to be save
      } else if (pq_substr($col_name, 0, 1)=="_") {
        // not a fiels, just for presentation purpose
      } else if (pq_ucfirst($col_name)==$col_name) {
        $depedantObjects[$col_name]=($this->$col_name);
      } else {
        $dataType=$this->getDataType($col_name);
        $dataLength=$this->getDataLength($col_name);
        if ($dataType=='int' and $dataLength==1) {
          if ($col_new_value==NULL or $col_new_value=="") {
            $col_new_value='0';
          }
        }
        $col_old_value=(property_exists($oldObject, $col_name))?$oldObject->$col_name:null;
        // special null treatment (new value)
        // $col_new_value=Sql::str(trim($col_new_value));
        if (get_class($this)!='Parameter') { // Do not trim parameters
          $col_new_value=pq_trim($col_new_value);
        }
        if ($dataType=='decimal') {
          $col_new_value=pq_str_replace(',', '.', $col_new_value);
        }
        if ($col_new_value=='') {
          $col_new_value=NULL;
        }
        // special null treatment (old value)
        // $col_old_value=SQL::str(trim($col_old_value));
        if ($col_old_value=='') {
          $col_old_value=NULL;
        }
        // if changed
        $isText=($dataType=='varchar' or pq_substr($dataType, -4)=='text')?true:false;
        if ($isText and $dataLength>4000 and (getEditorType()=='text' or Importable::importInProgress())) {
          $textObj=new Html2Text($col_old_value);
          $oldText=$textObj->getText();
          if (Importable::importInProgress()) {
            // $oldText=encodeCSV($oldText);
            $oldText=pq_str_replace("\n\n", "\n", $oldText); // Remove double LF as they were removed during export
            $oldText=pq_str_replace("\r", "", $oldText);
            $col_new_value=pq_str_replace("\r", "", $col_new_value); // Replace CRLF with LF
          }
          if (pq_trim($oldText)==pq_trim($col_new_value)) {
            $col_new_value=$col_old_value; // Was not changed : preserve formatting
          } else {
            $col_new_value=nl2brForPlainText($col_new_value);
          }
        }
        if ($col_new_value&&$isText and $dataLength>4000 and pq_substr(getEditorType(), 0, 2)=='CK') {
          // if (pq_strpos($col_new_value,'<script')!==false) {
          $pattern='/<style\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/style>/i';
          $replacement='';
          $col_new_value=preg_replace($pattern, $replacement, $col_new_value);
          // }
        }
        // !!! do not insert query for last update date time unless some change is detected
        if ($col_new_value!=$col_old_value or ($isText and ('x' . $col_new_value!='x' . $col_old_value))) {
          if (!$col_new_value and !$col_old_value and self::isAmountOrWork($col_name)) {
            continue; // do not save 0 to null or null to zero for Cost, Work and Amount
          }
          if (SqlElement::is_a($this, 'PlanningElement') and !$this->isManualProgress) {
            if (!isset($this->_workHistory) and ($col_name=='assignedWork' or $col_name=='leftWork' or $col_name=='plannedWork' or $col_name=='assignedCost' or $col_name=='leftCost' or $col_name=='plannedCost')) {
              continue; // Do not update calculated fields if not coming from function updateSynthesisObj()
            }
          }
          if ($col_name=='idle') {
            $idleChange=true;
          }
          if ($col_name=='idProject' and get_class($this)!='Project') {
            $projectChange=true;
          }
          $insertableColName=$this->getDatabaseColumnName($col_name);
          if (Sql::isPgsql()) {
            $insertableColName=pq_strtolower($insertableColName);
          }
          if (!pq_array_key_exists($insertableColName, $arrayCols)) {
            $arrayCols[$insertableColName]=$col_name;
            $query.=($nbChanged==0)?" set ":", ";
            if ($col_new_value==NULL or $col_new_value=='' or $col_new_value=="''") {
              $query.=$insertableColName . " = NULL";
            } else {
              $query.=$insertableColName . '=' . Sql::str($col_new_value) . ' ';
            }
            $nbChanged+=1;
            // Save change history
            if ($objectClass!='History' and !property_exists($this, '_noHistory') and $col_name!='id' and $col_name!='lastUpdateDateTime') {
              if (get_class($this)=='SubTask') {
                $result=History::store($this, $objectClass, $this->id, 'update', get_class($this), $col_old_value, $col_new_value);
              } else {
                $result=History::store($this, $objectClass, $this->id, 'update', $col_name, $col_old_value, $col_new_value);
              }
              if (!$result) {
                $returnStatus="ERROR";
                $returnValue=Sql::$lastQueryErrorMessage;
              }
            }
          }
        }
      }
    }
    if (($force or $nbChanged>0) and property_exists($this, 'lastUpdateDateTime')) {
      $insertableColName=$this->getDatabaseColumnName('lastUpdateDateTime');
      if (Sql::isPgsql()) {
        $insertableColName=pq_strtolower($insertableColName);
      }
      $query.=(($nbChanged==0)?' SET ':', ') . $insertableColName . '=' . Sql::str(date('Y-m-d H:i:s')) . ' ';
      $nbChanged+=1;
    }
    $query.=' where id=' . $this->id;
    // If changed, execute the query
    if ($nbChanged>0 and $returnStatus!="ERROR") {
      // Catch errors, and return error message
      $result=Sql::query($query);
      if ($result) {
        if (Sql::$lastQueryNbRows==0) {
          $test=new $objectClass($this->id, true);
          if ($this->id!=$test->id) {
            $returnValue=i18n('messageItemDelete', array(i18n(get_class($this)), $this->id));
            $returnStatus='ERROR';
          } else {
            $returnValue=i18n('messageNoChange') . ' ' . i18n(get_class($this)) . ' #' . $this->id;
            $returnStatus='NO_CHANGE';
          }
        } else {
          $returnValue=i18n(get_class($this)) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultUpdated');
          $returnStatus='OK';
        }
      } else {
        $returnValue=Sql::$lastQueryErrorMessage;
        $returnStatus="ERROR";
      }
    }

    // if object is Asignable, update assignments on idle change
    $archiv=new HistoryArchive();
    $hist=new History();
    if (property_exists($this, 'idle') and property_exists($this, '_Assignment') and $this->idle==1) { // PBER : add test so that only closed activty will close assignement, no automatic reopen
      $ass=new Assignment();
      $query="update " . $ass->getDatabaseTableName();
      $query.=" set idle='" . (($this->idle)?'1':'0') . "', leftWork='0'";
      $query.=" where refType='" . get_class($this) . "' ";
      $query.=" and refId=" . $this->id;
      $result=Sql::query($query);
      if (!$result) {
        $returnValue=Sql::$lastQueryErrorMessage;
        $returnStatus='ERROR';
      }
    }

    // Set notes on item to idle (or not)
    if (property_exists($this, 'idle') and property_exists($this, '_Note')) {
      $note=new Note();
      $query="update " . $note->getDatabaseTableName();
      $query.=" set idle='" . (($this->idle)?'1':'0') . "'";
      $query.=" where refType='" . get_class($this) . "' ";
      $query.=" and refId=" . $this->id;
      $result=Sql::query($query);
      if (!$result) {
        $returnValue=Sql::$lastQueryErrorMessage;
        $returnStatus='ERROR';
      }
    }
    if ($projectChange and $returnStatus!="ERROR") {
      $note=new Note();
      $query="update " . $note->getDatabaseTableName();
      $query.=" set idProject=" . ($this->idProject??'null');
      $query.=" where refType='" . get_class($this) . "' ";
      $query.=" and refId=" . $this->id;
      $result=Sql::query($query);
      if (!$result) {
        $returnValue=Sql::$lastQueryErrorMessage;
        $returnStatus='ERROR';
      }
    }

    // save depedant elements (properties that are objects)
    if ($returnStatus!="ERROR" and $returnStatus!="INVALID" and !$withoutDependencies) {
      $returnStatus=$this->saveDependantObjects($depedantObjects, $returnStatus);
      if ($returnStatus=="ERROR") {
        $returnValue=Sql::$lastQueryErrorMessage;
      } else if ($returnStatus=="OK") {
        $returnValue=i18n(get_class($this)) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultUpdated');
        // Dependant Changed but no change saved on main object : update LastUYPdateDateTime
        if ($this->id and !$force and $nbChanged==0 and property_exists($this, 'lastUpdateDateTime')) {
          $insertableColName=$this->getDatabaseColumnName('lastUpdateDateTime');
          if (Sql::isPgsql()) {
            $insertableColName=pq_strtolower($insertableColName);
          }
          $queryLastUpdate="UPDATE " . $this->getDatabaseTableName() . " SET " . $this->getDatabaseColumnName('lastUpdateDateTime') . '=' . Sql::str(date('Y-m-d H:i:s'));
          $queryLastUpdate.=" WHERE id=$this->id";
          Sql::query($queryLastUpdate);
        }
      } else if ($returnStatus=="NO_CHANGE" or $returnStatus=="INCOMPLETE" or $returnStatus=="WARNING" or $returnStatus=="CONFIRM") {
        // OK
      } else if (getLastOperationStatus($returnStatus)=='INVALID') {
        return $returnStatus;
      }
    }
    if ($returnStatus=="OK") {
      $returnValue.='${mailMsg}';
    }
    // Prepare return data
    $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    $returnValue.='<input type="hidden" id="lastOperation" value="update" />';
    $returnValue.='<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    return $returnValue;
  }

  /**
   * =========================================================================
   * Save the dependant objects stored in a list (may be single objects or list
   *
   * @param $depedantObjects Array
   *          list
   *          (array) of objects to store
   * @return void
   */
  private function saveDependantObjects($depedantObjects, $returnStatus) {
    $returnStatusDep=$returnStatus;
    foreach ($depedantObjects as $class=>$depObj) {
      if (is_array($depObj) and $returnStatusDep!="ERROR") {
        foreach ($depObj as $depClass=>$depObjOccurence) {
          if ($depObjOccurence instanceof SqlElement and $returnStatusDep!="ERROR") {
            $depObjOccurence->refId=$this->id;
            $depObjOccurence->refType=get_class($this);
            // ADD BY Marc TABARY - 2017-03-20 - INIT REFNAME OF ORGANIZATION'S BUDGET ELEMENT
            if (get_class($this)=='Organization') {
              $depObjOccurence->refName=$this->name;
            }
            // END ADD BY Marc TABARY - 2017-03-20 - INIT REFNAME OF ORGANIZATION'S BUDGET ELEMENT

            $ret=$depObjOccurence->saveSqlElement();
            if (pq_stripos($ret, 'id="lastOperationStatus" value="ERROR"')) {
              $returnStatusDep="ERROR";
            } else if (pq_stripos($ret, 'id="lastOperationStatus" value="OK"')) {
              $returnStatusDep='OK';
            }
          }
        }
      } else if ($depObj instanceof SqlElement and $returnStatusDep!="ERROR") {
        $depObj->refId=$this->id;
        $depObj->refType=get_class($this);
        if (get_class($depObj)=='WorkElement' and !$depObj->id) {
          $we=SqlElement::getSingleSqlElementFromCriteria('WorkElement', array('refType'=>$depObj->refType, 'refId'=>$depObj->refId));
          $depObj->id=$we->id;
        }
        if (get_class($depObj)=='VotingItem' and !Module::isModuleActive('moduleVoting')) continue;
        if (get_class($depObj)=='VotingItem' and !$depObj->id) {
          $vi=SqlElement::getSingleSqlElementFromCriteria('VotingItem', array('refType'=>$depObj->refType, 'refId'=>$depObj->refId));
          $depObj->id=$vi->id;
        }
        // ADD BY Marc TABARY - 2017-03-20 - INIT REFNAME OF ORGANIZATION'S BUDGET ELEMENT
        if (get_class($this)=='Organization') {
          $depObj->refName=$this->name;
        }
        // END ADD BY Marc TABARY - 2017-03-20 - INIT REFNAME OF ORGANIZATION'S BUDGET ELEMENT
        $ret=$depObj->save();
        if (pq_stripos($ret, 'id="lastOperationStatus" value="ERROR"')) {
          $returnStatusDep="ERROR";
        } else if (pq_stripos($ret, 'id="lastOperationStatus" value="INVALID"')) {
          $returnStatusDep=$ret;
        } else if (pq_stripos($ret, 'id="lastOperationStatus" value="OK"')) {
          $returnStatusDep='OK';
        }
      }
    }
    return $returnStatusDep;
  }

  /**
   * =========================================================================
   * Delete an object from the database
   *
   * @return void
   */
  private function deleteSqlElement() {
    if (!$this->id or $this->id<0) {
      return;
    }
    $class=get_class($this);
    $control=$this->deleteControl();
    if (($control=='OK' or pq_strpos($control, 'id="confirmControl" value="delete"')>0) and property_exists($class, $class . 'PlanningElement')) {
      $pe=$class . 'PlanningElement';
      $controlPe=$this->$pe->deleteControl();
      if ($controlPe!='OK') {
        $control=$controlPe;
      }
    }
    global $adminFunctionality;
    if (isset($adminFunctionality) and $adminFunctionality=="checkConsistency") {
      $control='OK';
    }

    if ($control!="OK") {
      // errors on control => don't save, display error message
      if (pq_strpos($control, 'id="confirmControl" value="delete"')>0) {
        $returnValue='<b>' . i18n('messageConfirmationNeeded') . '</b><br/>' . $control;
        $returnValue.='<input type="hidden" id="lastOperationStatus" value="CONFIRM" />';
      } else {
        $returnValue='<b>' . i18n('messageInvalidControls') . '</b><br/>' . $control;
        $returnValue.='<input type="hidden" id="lastOperationStatus" value="INVALID" />';
      }
      $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
      $returnValue.='<input type="hidden" id="lastOperation" value="control" />';

      return $returnValue;
    }
    foreach ($this as $col_name=>$col_value) {
      // if property is an array containing objects, delete each
      if (is_array($this->$col_name)) {
        foreach ($this->$col_name as $obj) {
          if ($obj instanceof SqlElement) {
            if ($obj->id and $obj->id!='') { // object may be a "new" element, so try to delete only if id exists
              $obj->delete();
            }
          }
        }
      } else if (pq_ucfirst($col_name)==$col_name) {
        // if property is an object, delete it
        if ($this->$col_name instanceof SqlElement) {
          if ($this->$col_name->id and $this->$col_name->id!='') { // object may be a "new" element, so try to delete only if id exists
            $resSub=$this->$col_name->delete();
          }
        }
      }
    }
    // check relartionship : if "cascade", then auto delete
    $relationShip=self::$_relationShip;
    $canForceDelete=false;
    if (getSessionUser()->id) {
      $user=getSessionUser();
      $crit=array('idProfile'=>$user->getProfile($this), 'scope'=>'canForceDelete');
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
      if ($habil and $habil->id and $habil->rightAccess=='1') {
        $canForceDelete=true;
      }
    }
    $canDeleteRealWork=false;
    $crit=array('idProfile'=>getSessionUser()->getProfile($this), 'scope'=>'canDeleteRealWork');
    $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
    if ($habil and $habil->id and $habil->rightAccess=='1') {
      $canDeleteRealWork=true;
    }
    $returnStatus="OK";
    $returnValue='';
    if ($class=='TicketSimple') {
      $class='Ticket';
    }
    if (pq_array_key_exists($class, $relationShip)) {
      $relations=$relationShip[$class];
      $relations['Alert']='cascade';
      $relations['IndicatorValue']='cascade';
      if ($class=='User' or $class=='Contact') $relations['ResourceTeamAffectation']='cascade';
      foreach ($relations as $object=>$mode) {
        if ($mode=="control" and $canForceDelete) {
          $mode="confirm";
        } else if ($mode=="controlStrict") {
          if ($object=='Work' and $canDeleteRealWork) $mode="confirm";
          else $mode="control";
        }
        if ($mode=="cascade" or ($mode=="confirm" and self::isDeleteConfirmed())) {
          $where=null;
          $obj=new $object();
          $crit=array($obj->getDatabaseColumnName('id' . $class)=>$this->id);
          if ($class=='AccessProfileNoProject') {
            $crit=array('idAccessProfile'=>$this->id);
          }
          if ($class=='ComponentVersion' and $object=='ProductAsset') {
            $crit=array($obj->getDatabaseColumnName('idProductVersion')=>$this->id);
          }
          if (property_exists($obj, 'refType') and property_exists($obj, 'refId')) {
            if (property_exists($obj, 'id' . $class)) {
              $crit=null;
              $where=$obj->getDatabaseColumnName("id" . $class) . "=" . $this->id . " or (refType='" . $class . "' and refId=" . $this->id . ")";
            } else {
              $crit=array("refType"=>$class, "refId"=>$this->id);
            }
          }
          if ($object=='VersionProject' and ($class=='ProductVersion' or $class=='ComponentVersion')) {
            $crit=array('idVersion'=>$this->id);
          }
          if ($object=="Dependency") {
            $crit=null;
            $where="(predecessorRefType='" . $class . "' and predecessorRefId=" . Sql::fmtId($this->id) . ")" . " or (successorRefType='" . $class . "' and successorRefId=" . Sql::fmtId($this->id) . ")";
          }
          if ($object=="Link") {
            $crit=null;
            $where="(ref1Type='" . $class . "' and ref1Id=" . Sql::fmtId($this->id) . ")" . " or (ref2Type='" . $class . "' and ref2Id=" . Sql::fmtId($this->id) . ")";
          }
          if ($object=="WorkflowStatus" and $class=='Status') {
            $crit=null;
            $where="idStatusFrom=" . Sql::fmtId($this->id) . " or idStatusTo=" . Sql::fmtId($this->id);
          }
          if ($class=='ResourceTeam' and $object!='ResourceTeamAffectation') {
            $crit=array('idResource'=>$this->id);
          }
          if (($class=='User' or $class=='Contact') and $object=='ResourceTeamAffectation') {
            $crit=array('idResource'=>$this->id);
          }
          if ($class=='TokenDefinition' and $object=='WorkTokenMarkup') {
            $crit=array('idWorkToken'=>$this->id);
          }
          $list=$obj->getSqlElementsFromCriteria($crit, false, $where);
          foreach ($list as $subObj) {
            $subObjDel=new $object($subObj->id);
            $resSub=$subObjDel->delete();
            $statusSub=getLastOperationStatus($resSub);
            if ($statusSub=='INVALID' or $statusSub=='ERROR') {
              $returnStatus=$statusSub;
              $returnValue=$resSub;
              // $returnValue = "$object #$subObj->id <br/><br/>" . getLastOperationMessage ( $resSub );
              break;
            }
          }
        }
      }
    }
    if ($returnStatus=="OK") { // May have errors deleting dependant elements
      $query="delete from " . $this->getDatabaseTableName() . " where id=" . Sql::fmtId($this->id) . "";
      // execute request
      $result=Sql::query($query);
      if (!$result) {
        $returnStatus="ERROR";
      } else {
        // PBER #11458 - Pirge not needed and leads to deadlocks
        // $peName = get_class ( $this ) . 'PlanningElement';
        // if (property_exists ( $this, $peName )) {
        // $pe = new PlanningElement ();
        // $pe->purge ( ' refName is null' );
        // }
      }
    }
    // delete tag list is object tag
    if (property_exists($this, 'tags')) {
      Tag::saveTagList(null, $this->tags, get_class($this));
    }
    // save history
    if ($returnStatus!="ERROR" and !property_exists($this, '_noHistory')) {
      $result=History::store($this, $class, $this->id, 'delete');
      if (!$result) {
        $returnStatus="ERROR";
      }
    }
    if ($returnValue=='') { // If $returnValue set from sub object, do not override with possibly empty.
      if ($returnStatus!="ERROR") {
        $returnValue=i18n($class) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultDeleted');
      } else {
        $returnValue=Sql::$lastQueryErrorMessage;
      }
    }
    $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    $returnValue.='<input type="hidden" id="lastOperation" value="delete" />';
    $returnValue.='<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    $returnValue.='<input type="hidden" id="noDataMessage" value="' . pq_str_replace('"', "'", htmlGetNoDataMessage(get_class($this))) . '" />';
    return $returnValue;
  }

  /**
   * =========================================================================
   * Purge objects from the database : delete all objects corresponding
   * to clause $ clause
   * Important :
   * => does not automatically purges included elements ...
   * => does not include history insertion
   *
   * @return void
   */
  private function purgeSqlElement($clause) {
    $objectClass=get_class($this);
    // purge depending Planning Element if any
    if (property_exists($this, $objectClass . 'PlanningElement')) {
      $query="select id from " . $this->getDatabaseTableName() . " where " . $clause;
      $resultId=Sql::query($query);
      if (Sql::$lastQueryNbRows>0) {
        $line=Sql::fetchLine($resultId);
        $peCrit='(0';
        while ($line) {
          $peCrit.=',' . $line['id'];
          $line=Sql::fetchLine($resultId);
        }
        $peCrit.=')';
        $pe=new PlanningElement();
        $query="delete from " . $pe->getDatabaseTableName() . " where refType='$objectClass' and refId in $peCrit";
        Sql::query($query);
      }
    }
    // get all data, and identify if changes
    $query="delete from " . $this->getDatabaseTableName() . " where " . $clause;
    // execute request
    $returnStatus="OK";
    $result=Sql::query($query);
    if (!$result) {
      $returnStatus="ERROR";
    }
    if ($returnStatus!="ERROR") {
      $returnValue=Sql::$lastQueryNbRows . " " . i18n(get_class($this)) . '(s) ' . i18n('doneoperationdelete');
    } else {
      $returnValue=Sql::$lastQueryErrorMessage;
    }
    $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    $returnValue.='<input type="hidden" id="lastOperation" value="delete" />';
    $returnValue.='<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    $returnValue.='<input type="hidden" id="noDataMessage" value="' . htmlGetNoDataMessage(get_class($this)) . '" />';
    return $returnValue;
  }

  /**
   * =========================================================================
   * Close objects from the database : delete all objects corresponding
   * to clause $ clause
   * Important :
   * => does not automatically purges included elements ...
   * => does not include history insertion
   *
   * @return void
   */
  private function closeSqlElement($clause) {
    $objectClass=get_class($this);
    // get all data, and identify if changes
    $query="update " . $this->getDatabaseTableName() . " set idle='1' where " . $clause;
    // execute request
    $returnStatus="OK";
    $result=Sql::query($query);
    if (!$result) {
      $returnStatus="ERROR";
    }
    if ($returnStatus!="ERROR") {
      $returnValue=Sql::$lastQueryNbRows . " " . i18n(get_class($this)) . '(s) ' . i18n('doneoperationclose');
    } else {
      $returnValue=Sql::$lastQueryErrorMessage;
    }
    $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($this->id) . '" />';
    $returnValue.='<input type="hidden" id="lastOperation" value="update" />';
    $returnValue.='<input type="hidden" id="lastOperationStatus" value="' . $returnStatus . '" />';
    $returnValue.='<input type="hidden" id="noDataMessage" value="' . htmlGetNoDataMessage(get_class($this)) . '" />';
    return $returnValue;
  }

  /**
   * =========================================================================
   * Copy the curent object as a new one of the same class
   *
   * @return Object the new object
   */
  private function copySqlElement() {
    $newObj=clone $this;
    $newObj->id=null;
    if (property_exists($newObj, "wbs")) {
      $newObj->wbs=null;
    }
    if (property_exists($newObj, "topId")) {
      $newObj->topId=null;
    }
    if (property_exists($newObj, "idStatus")) {
      if (get_class($newObj)=='TestSession') {
        $list=SqlList::getList('Status');
        $revert=array_keys($list);
        $newObj->idStatus=$revert[0];
      } else {
        $st=SqlElement::getSingleSqlElementFromCriteria('Status', array('isCopyStatus'=>'1'));
        if (!$st or !$st->id) {
          errorLog("Error : several or no status exist with isCopyStatus=1 (expected is 1 only and only 1)");
        }
        $newObj->idStatus=$st->id;
      }
    }
    if (property_exists($newObj, "idUser") and get_class($newObj)!='Affectation' and get_class($newObj)!='Message' and get_class($newObj)!='VotingAttribution') {
      $newObj->idUser=getSessionUser()->id;
    }
    if (property_exists($newObj, "creationDate")) {
      $newObj->creationDate=date('Y-m-d');
    }
    if (property_exists($newObj, "creationDateTime")) {
      $newObj->creationDateTime=date('Y-m-d H:i');
    }
    if (property_exists($newObj, "lastUpdateDateTime")) {
      $newObj->lastUpdateDateTime=null;
    }
    if (property_exists($newObj, "done")) {
      $newObj->done=0;
    }
    if (property_exists($newObj, "idle")) {
      $newObj->idle=0;
    }
    if (property_exists($newObj, "idleDate")) {
      $newObj->idleDate=null;
    }
    if (property_exists($newObj, "doneDate")) {
      $newObj->doneDate=null;
    }
    if (property_exists($newObj, "idleDateTime")) {
      $newObj->idleDateTime=null;
    }
    if (property_exists($newObj, "doneDateTime")) {
      $newObj->doneDateTime=null;
    }
    if (property_exists($newObj, "reference")) {
      $newObj->reference=null;
    }
    if (property_exists($newObj, "password")) {
      $newObj->password=null;
    }
    if (property_exists($newObj, "apiKey")) {
      $newObj->apiKey=md5($this->id . date('Ymdhis'));
    }
    if (property_exists($newObj, "idRunStatus")) {
      $newObj->idRunStatus=5;
    }
    if (property_exists($newObj, "idSituation")) {
      $newObj->idSituation=null;
    }
    foreach ($newObj as $col_name=>$col_value) {
      if (pq_ucfirst($col_name)==$col_name) {
        // if property is an object, delete it
        if ($newObj->$col_name instanceof SqlElement) {
          $newObj->$col_name->id=null;
          if (property_exists($newObj->$col_name, "wbs")) {
            $newObj->$col_name->wbs=null;
          }
          if (property_exists($newObj->$col_name, "topId")) {
            $newObj->$col_name->topId=null;
          }
          if ($newObj->$col_name instanceof PlanningElement) {
            $newObj->$col_name->plannedStartDate="";
            $newObj->$col_name->realStartDate="";
            $newObj->$col_name->plannedEndDate="";
            $newObj->$col_name->realEndDate="";
            $newObj->$col_name->plannedDuration="";
            $newObj->$col_name->realDuration="";
            $newObj->$col_name->assignedWork=0;
            $newObj->$col_name->plannedWork=0;
            $newObj->$col_name->leftWork=0;
            $newObj->$col_name->realWork=0;
            $newObj->$col_name->notPlannedWork=0;
            $newObj->$col_name->idle=0;
            $newObj->$col_name->done=0;
          }
        }
      }
    }
    if (get_class($this)=='User') {
      $newObj->name=i18n('copiedFrom') . ' ' . $newObj->name;
      if ($newObj->resourceName) {
        $newObj->resourceName=i18n('copiedFrom') . ' ' . $newObj->resourceName;
      }
    } else if (get_class($newObj)=='Resource' or get_class($newObj)=='Contact' or get_class($newObj)=='Employee') {
      $newObj->name=i18n('copiedFrom') . ' ' . $newObj->name;
      if ($newObj->userName) {
        $newObj->userName=i18n('copiedFrom') . ' ' . $newObj->userName;
      }
    }
    if (is_a($this, 'Version') and $newObj->versionNumber) {
      $existWithName=$newObj->countSqlElementsFromCriteria(null, "name='" . Sql::fmtStr($newObj->name) . "'");
      if ($existWithName>0) {
        $newObj->versionNumber=$newObj->versionNumber . ' (' . i18n('copy') . ')';
        $newObj->name=$newObj->name . ' (' . i18n('copy') . ')';
      }
    }
    if (property_exists($newObj, "isCopyStatus")) {
      $newObj->isCopyStatus=0;
    }

    foreach ($this as $col_name=>$col_value) {
      if (pq_strpos($newObj->getFieldAttributes($col_name), 'unique')!==false) {
        $dataType=$newObj->getDataType($col_name);
        if ($dataType=='varchar' or $dataType=='text') {
          $where='UPPER(' . $this->getDatabaseColumnName($col_name) . ")=" . Sql::str(pq_strtoupper($col_value));
          if ($newObj->id) $where.=" and id<>" . $newObj->id;
          $count=$newObj->countSqlElementsFromCriteria(null, $where);
          if ($count>0) {
            if (get_class($this)) {
              $list=SqlList::getList(get_class($this), $col_name);
              if ($col_name=='description' or $col_name=='result') {
                $newObj->$col_name="<div> " . i18n('copy') . " (1)</div>" . $this->$col_name;
                $i=2;
                $copies=[$this->$col_name];
                while (in_array($newObj->$col_name, $list)) {
                  $newObj->$col_name=preg_replace("/<div> " . i18n('copy') . " \\((\\d+)\\)<\\/div>/", "<div> " . i18n('copy') . " ($i)</div>", $newObj->$col_name);
                  $i++;
                  $copies[]=$newObj->$col_name;
                }
              } else {
                $newObj->$col_name=$this->$col_name . ' ' . i18n('copy') . ' (1)';
                $i=2;
                $copies=[$this->$col_name];
                while (in_array($newObj->$col_name, $list)) {
                  $newObj->$col_name=$this->$col_name . ' ' . i18n('copy') . ' (' . $i . ')';
                  $i++;
                  $copies[]=$newObj->$col_name;
                }
              }
            }
          }
        }
      }
    }
    $result=$newObj->save();
    if (get_class($newObj)=='Milestone') $newObj->MilestonePlanningElement->save();
    Sql::$lastCopyId=$newObj->id;
    if (pq_stripos($result, 'id="lastOperationStatus" value="OK"')>0) {
      $returnValue=i18n(get_class($this)) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultCopied') . ' #' . $newObj->id;
      $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($newObj->id) . '" />';
      $returnValue.='<input type="hidden" id="lastOperation" value="copy" />';
      $returnValue.='<input type="hidden" id="lastOperationStatus" value="OK" />';
    } else {
      $returnValue=$result;
    }
    $newObj->_copyResult=$returnValue;
    return $newObj;
  }

  private function copySqlElementTo($newClass, $newType, $newName, $newProject, $setOrigin, $withNotes, $withAttachments, $withLinks, $withAssignments=false, $withAffectations=false, $toProject=null, $toActivity=null, $copyToWithResult=false, $copyToWithStatus=true, $copyToWithSubTask=false, $moveAfterCreate=null) {
    $newObj=new $newClass();
    $newObj->id=null;
    // $typeName = 'id' . $newClass . 'Type';
    ($newClass=='PeriodicMeeting')?$typeName='idMeetingType':$typeName='id' . $newClass . 'Type';
    $typeName=SqlElement::getTypeName($newClass);
    // $typeClass=pq_substr($typeName,2);
    $typeClass=SqlElement::getTypeClassName($newClass);
    if ($newClass!="CatalogUO") {
      $newObj->$typeName=$newType;
    }
    if ($setOrigin and property_exists($newObj, 'Origin')) {
      $newObj->Origin->originType=get_class($this);
      $newObj->Origin->originId=$this->id;
      $newObj->Origin->refType=$newClass;
    }
    foreach ($newObj as $col_name=>$col_value) {
      if (pq_ucfirst($col_name)==$col_name) {
        if ($newObj->$col_name instanceof PlanningElement) {
          $sub=pq_substr($col_name, 0, pq_strlen($col_name)-15);
          $plMode='id' . $sub . 'PlanningMode';
          $pm=null;
          if (get_class($this)==$newClass and $newClass!='Project') {
            $pm=$this->$col_name->$plMode;
          } else if ($newClass!='Project') {
            $t=new $typeClass($newType);
            if (property_exists($t, $plMode)) {
              $pm=$t->$plMode;
            } else {
              $lst=SqlList::getList(pq_substr($plMode, 2));
              if (count($lst)>0) {
                foreach ($lst as $id=>$val) {
                  $pm=$id;
                  break;
                }
              }
            }
            if (property_exists($newObj, 'idPlanningMode')) $newObj->idPlanningMode=$pm;
            $newObj->$col_name->$plMode=$pm;
          }
          $newObj->$col_name->refName=$newName;
        }
      }
    }
    foreach ($this as $col_name=>$col_value) {
      if (pq_ucfirst($col_name)==$col_name) {
        if ($this->$col_name instanceof SqlElement) {
          // $newObj->$col_name->id=null;
          if ($this->$col_name instanceof PlanningElement) {
            $pe=$newClass . 'PlanningElement';
            if (property_exists($newObj, $pe)) {
              if (get_class($this)==$newClass) {
                $plMode='id' . $newClass . 'PlanningMode';
                if (property_exists($this->$col_name, $plMode)) {
                  $newObj->$col_name->$plMode=$this->$col_name->$plMode;
                }
              }
              $newObj->$pe->initialStartDate=$this->$col_name->initialStartDate;
              $newObj->$pe->initialEndDate=$this->$col_name->initialEndDate;
              $newObj->$pe->initialDuration=$this->$col_name->initialDuration;
              $newObj->$pe->validatedStartDate=$this->$col_name->validatedStartDate;
              $newObj->$pe->validatedEndDate=$this->$col_name->validatedEndDate;
              $newObj->$pe->validatedDuration=$this->$col_name->validatedDuration;
              $newObj->$pe->validatedWork=$this->$col_name->validatedWork;
              $newObj->$pe->validatedCost=$this->$col_name->validatedCost;
              $newObj->$pe->priority=$this->$col_name->priority;
              // $newObj->$pe->topId=$this->$col_name->topId;
              $newObj->$pe->topRefType=$this->$col_name->topRefType;
              $newObj->$pe->topRefId=$this->$col_name->topRefId;
              if (property_exists($this->$col_name, 'color')) {
                $newObj->$pe->color=$this->$col_name->color;
              }
              if ($moveAfterCreate) {
                $newObj->$pe->_moveToAfterCreate=$moveAfterCreate;
              }
            }
          }

          // ADD BY Marc TABARY - 2017-02-09
          if ($this->$col_name instanceof BudgetElement) {
            $newObj->$col_name->budgetWork=0;
            $newObj->$col_name->validatedWork=0;
            $newObj->$col_name->assignedWork=0;
            $newObj->$col_name->realWork=0;
            $newObj->$col_name->leftWork=0;
            $newObj->$col_name->plannedWork=0;
            $newObj->$col_name->budgetCost=null;
            $newObj->$col_name->validatedCost=null;
            $newObj->$col_name->assignedCost=null;
            $newObj->$col_name->realCost=null;
            $newObj->$col_name->leftCost=null;
            $newObj->$col_name->plannedCost=null;
            $newObj->$col_name->progress=0;
            $newObj->$col_name->expenseBudgetAmount=null;
            $newObj->$col_name->expenseAssignedAmount=null;
            $newObj->$col_name->expensePlannedAmount=null;
            $newObj->$col_name->expenseRealAmount=null;
            $newObj->$col_name->expenseLeftAmount=null;
            $newObj->$col_name->expenseValidatedAmount=null;
            $newObj->$col_name->totalBudgetCost=null;
            $newObj->$col_name->totalAssignedCost=null;
            $newObj->$col_name->totalPlannedCost=null;
            $newObj->$col_name->totalRealCost=null;
            $newObj->$col_name->totalLeftCost=null;
            $newObj->$col_name->totalValidatedCost=null;
            $newObj->$col_name->reserveAmount=null;
            $newObj->$col_name->idle=0;
            // ADD BY Marc TABARY - 2017-03-09 - PERIODIC YEAR BUDGET ELEMENT
            $newObj->$col_name->idleDateTime=null;
            // END ADD BY Marc TABARY - 2017-03-09 - PERIODIC YEAR BUDGET ELEMENT
          }
          // END ADD BY Marc TABARY - 2017-02-09
        }
      } else if (property_exists($newObj, $col_name)) {
        if ($col_name!='id' and $col_name!="wbs" and $col_name!='name' and $col_name!=$typeName and $col_name!="handled" and $col_name!="handledDate" and $col_name!="handledDateTime" and $col_name!="done" and $col_name!="doneDate" and $col_name!="doneDateTime" and $col_name!="idle" and $col_name!="idleDate" and $col_name!="idleDateTime" and $col_name!="idStatus" and $col_name!="reference" and $col_name!="billId") { // topId ?
          $newObj->$col_name=$this->$col_name;
        }
      }
      if (pq_strpos($newObj->getFieldAttributes($col_name), 'unique')!==false) {
        $dataType=$newObj->getDataType($col_name);
        if ($dataType=='varchar' or $dataType=='text') {
          $where='UPPER(' . $this->getDatabaseColumnName($col_name) . ")=" . Sql::str(pq_strtoupper($col_value));
          if ($newObj->id) $where.=" and id<>" . $newObj->id;
          $count=$newObj->countSqlElementsFromCriteria(null, $where);
          if ($count>0) {
            if (get_class($this)) {
              $list=SqlList::getList(get_class($this), $col_name);
              if ($col_name=='description' or $col_name=='result') {
                $newObj->$col_name="<div> " . i18n('copy') . " (1)</div>" . $this->$col_name;
                $i=2;
                $copies=[$this->$col_name];
                while (in_array($newObj->$col_name, $list)) {
                  $newObj->$col_name=preg_replace("/<div> " . i18n('copy') . " \\((\\d+)\\)<\\/div>/", "<div> " . i18n('copy') . " ($i)</div>", $newObj->$col_name);
                  $i++;
                  $copies[]=$newObj->$col_name;
                }
              } else {
                $newObj->$col_name=$this->$col_name . ' ' . i18n('copy') . ' (1)';
                $i=2;
                $copies=[$this->$col_name];
                while (in_array($newObj->$col_name, $list)) {
                  $newObj->$col_name=$this->$col_name . ' ' . i18n('copy') . ' (' . $i . ')';
                  $i++;
                  $copies[]=$newObj->$col_name;
                }
              }
            }
          }
        }
      }
    }
    if (property_exists($newObj, "idProject") and $toProject) {
      $newObj->idProject=$toProject;
    }
    if (property_exists($newObj, "idStatus")) {
      $allowedStatusList=($copyToWithStatus)?Workflow::getAllowedStatusListForObject($newObj):null;
      if (isset($allowedStatusList) and count($allowedStatusList)>0) {
        $st=reset($allowedStatusList);
      } else {
        $st=SqlElement::getSingleSqlElementFromCriteria('Status', array('isCopyStatus'=>'1'));
        if (!$st or !$st->id) {
          errorLog("Error : several on no status exist with isCopyStatus=1");
        }
      }
      $newObj->idStatus=$st->id;
    }
    if (property_exists($newObj, "idUser") and get_class($newObj)!='Affectation' and get_class($newObj)!='Message' and get_class($newObj)!='VotingAttribution') {
      $newObj->idUser=getSessionUser()->id;
    }
    if (property_exists($newObj, "paymentAmount")) {
      $newObj->paymentAmount=null;
    }
    if (property_exists($newObj, "paymentDate")) {
      $newObj->paymentDate=null;
    }
    if (property_exists($newObj, "creationDate")) {
      $newObj->creationDate=date('Y-m-d');
    }
    if (property_exists($newObj, "creationDateTime")) {
      $newObj->creationDateTime=date('Y-m-d H:i');
    }
    if (property_exists($newObj, "lastUpdateDateTime")) {
      $newObj->lastUpdateDateTime=null;
    }
    if (property_exists($newObj, "meetingDate")) {
      $newObj->meetingDate=date('Y-m-d');
    }
    if (property_exists($newObj, "reference")) {
      $newObj->reference=null;
    }
    if (property_exists($newObj, "idActivity") and $toActivity) {
      $newObj->idActivity=$toActivity;
    }
    if (property_exists($newObj, "fixPerimeter")) {
      $newObj->fixPerimeter=0;
      $newObj->allowReduction=0;
    }
    // gautier #4404
    if (get_class($newObj)=='Asset') {
      $newObj->serialNumber=null;
      $newObj->inventoryNumber=null;
      $newObj->installationDate=null;
      $newObj->decommissioningDate=null;
    }
    if (get_class($newObj)=='Bill') {
      $newObj->paymentDate=null;
      $newObj->paymentAmount=null;
      $newObj->paymentDone=null;
      $newObj->paymentsCount=null;
      $newObj->date=date('Y-m-d');
      $newObj->sendDate=null;
      $newObj->idDeliveryMode=null;
    }
    if (property_exists($newObj, "sendDate")) {
      $newObj->sendDate=null;
    }
    if (property_exists($newObj, "paymentDate")) {
      $newObj->paymentDate=null;
    }
    if (property_exists($newObj, "paymentAmount")) {
      $newObj->paymentAmount=null;
    }
    if (property_exists($newObj, "paymentDone")) {
      $newObj->paymentDone=null;
    }
    if (property_exists($newObj, "paymentsCount")) {
      $newObj->paymentsCount=null;
    }
    if (property_exists($newObj, "checked")) {
      $newObj->checked=null;
    }

    if (get_class($newObj)=='ProviderPayment') {
      $newObj->idPaymentMode=SqlList::getFirstId('PaymentMode');
      $newObj->paymentDate=date('Y-m-d');
      if (property_exists($this, 'totalFullAmount')) {
        $newObj->paymentAmount=$this->totalFullAmount;
      } else if (property_exists($this, 'fullAmount')) {
        $newObj->paymentAmount=$this->fullAmount;
      }
      if (get_class($this)=='ProviderTerm') {
        $newObj->idProviderTerm=$this->id;
      } else if (get_class($this)=='ProviderBill') {
        $newObj->idProviderBill=$this->id;
      }
    }

    $newObj->name=$newName;
    if (!$toProject and property_exists($newObj, 'idProject') and $newProject) {
      $newObj->idProject=$newProject;
      if ($newObj->idProject!=$this->idProject and property_exists($newObj, 'idActivity')) {
        $pAct=new Activity($newObj->idActivity, true);
        if ($newObj->idProject!=$pAct->idProject) $newObj->idActivity=null;
      }
    }
    // check description
    if (property_exists($newObj, 'description') and !$newObj->description) {
      // $idType = 'id' . $newClass . 'Type';
      $idType=self::getTypeName($newClass);
      if (property_exists($newObj, $idType)) {
        // $type = $newClass . 'Type';
        $type=self::getTypeClassName($newClass);
        $objType=new $type($newObj->$idType);
        if (property_exists($objType, 'mandatoryDescription') and $objType->mandatoryDescription) {
          $newObj->description=$newObj->name;
        }
      }
    }
    if (!$copyToWithResult and property_exists($newObj, "result")) {
      $newObj->result=null;
    }
    if (!$copyToWithResult and property_exists($newObj, "idResolution")) {
      $newObj->idResolution=null;
    }
    if ($newClass=='Bill' and property_exists($this, 'validatedEndDate') and $this->validatedEndDate) {
      $newObj->date=$this->validatedEndDate;
    }
    $result=$newObj->save();
    if (get_class($newObj)=='Milestone') $newObj->MilestonePlanningElement->save();
    if (getLastOperationStatus($result)=='OK') {
      $returnValue=i18n(get_class($this)) . ' #' . htmlEncode($this->id) . ' ' . i18n('resultCopied') . ' #' . $newObj->id;
      $returnValue.='<input type="hidden" id="lastSaveId" value="' . htmlEncode($newObj->id) . '" />';
      $returnValue.='<input type="hidden" id="lastOperation" value="copy" />';
      $returnValue.='<input type="hidden" id="lastOperationStatus" value="OK" />';
    } else {
      $returnValue=$result;
    }
    if (getLastOperationStatus($result)=='OK' and $withNotes and property_exists($this, "_Note") and property_exists($newObj, "_Note")) {
      $crit=array('refType'=>get_class($this), 'refId'=>$this->id);
      $note=new Note();
      $notes=$note->getSqlElementsFromCriteria($crit);
      foreach ($notes as $note) {
        $note->id=null;
        $note->refType=get_class($newObj);
        $note->refId=$newObj->id;
        $note->save();
      }
    }

    if (getLastOperationStatus($result)=='OK' and $withLinks) {
      $crit=array('ref1Type'=>get_class($this), 'ref1Id'=>$this->id);
      $link=new Link();
      $links=$link->getSqlElementsFromCriteria($crit);
      foreach ($links as $link) {
        $link->id=null;
        $link->ref1Type=get_class($newObj);
        $link->ref1Id=$newObj->id;
        $link->save();
      }
      $crit=array('ref2Type'=>get_class($this), 'ref2Id'=>$this->id);
      $link=new Link();
      $links=$link->getSqlElementsFromCriteria($crit);
      foreach ($links as $link) {
        $link->id=null;
        $link->ref2Type=get_class($newObj);
        $link->ref2Id=$newObj->id;
        $link->save();
      }
    }
    // Gautier copy ActivitySkill
    if (getLastOperationStatus($result)=='OK' and $newClass=='Activity' and get_class($this)=='Activity') {
      if (Module::isModuleActive('moduleSkillManagement')) {
        $activitySkill=new ActivitySkill();
        $lstActivitySkill=$activitySkill->getSqlElementsFromCriteria(array('idActivity'=>$this->id));
        foreach ($lstActivitySkill as $skill) {
          $activitySkill=new ActivitySkill();
          $activitySkill->idActivity=$newObj->id;
          $activitySkill->idSkill=$skill->idSkill;
          $activitySkill->idSkillLevel=$skill->idSkillLevel;
          $activitySkill->save();
        }
      }
    }
    if (getLastOperationStatus($result)=='OK' and $newClass=='Acceptance' and get_class($this)=='Delivery') {
      if ($this->_Link_Activity) {
        foreach ($this->_Link_Activity as $activity) {
          $workCommandDone=new WorkCommandDone();
          $workCommandDoneList=$workCommandDone->getSqlElementsFromCriteria(array('refType'=>'Activity', 'refId'=>$activity->ref1Id));
          $acceptedQuantity=0;
          $doneQuantity=0;
          foreach ($workCommandDoneList as $workCommandDone) {
            $doneQuantity+=$workCommandDone->doneQuantity;
            $workCommandAccepted=new WorkCommandAccepted();
            $workCommandAcceptedList=$workCommandAccepted->getSqlElementsFromCriteria(array(
                'refType'=>'Activity',
                'refId'=>$activity->ref1Id,
                'idWorkCommand'=>$workCommandDone->idWorkCommand));
            foreach ($workCommandAcceptedList as $workCommandAccepted) {
              $acceptedQuantity+=$workCommandAccepted->acceptedQuantity;
            }
          }
          if (($doneQuantity-$acceptedQuantity)>0) {
            $link=new Link();
            $link->ref1Type=$activity->ref1Type;
            $link->ref1Id=$activity->ref1Id;
            $link->ref2Type=get_class($newObj);
            $link->ref2Id=$newObj->id;
            $link->save();
          }
        }
      }
    }
    if (getLastOperationStatus($result)=='OK' and $newClass=='Bill' and get_class($this)=='Acceptance') {
      $workCommandAccepted=new WorkCommandAccepted();
      $workCommandAcceptedList=$workCommandAccepted->getSqlElementsFromCriteria(array('idAcceptance'=>$this->id));
      foreach ($workCommandAcceptedList as $workCommandAccepted) {
        $workCommandBilled=WorkCommandBilled::getSingleSqlElementFromCriteria('WorkCommandBilled', array(
            'idWorkCommand'=>$workCommandAccepted->idWorkCommand));
        if (!$workCommandBilled->id) {
          $workCommandBilled->idCommand=$workCommandAccepted->idCommand;
          $workCommandBilled->billedQuantity=$workCommandAccepted->acceptedQuantity;
          $workCommandBilled->idBill=$newObj->id;
          $workCommandBilled->save();
        }
      }
    }
    if (getLastOperationStatus($result)=='OK' and $withAttachments) {
      $crit=array('refType'=>get_class($this), 'refId'=>$this->id);
      $attachment=new Attachment();
      $attachments=$attachment->getSqlElementsFromCriteria($crit);
      $pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
      $attachmentDirectory=Parameter::getGlobalParameter('paramAttachmentDirectory');
      foreach ($attachments as $attachment) {
        $fromdir=$attachmentDirectory . $pathSeparator . "attachment_" . $attachment->id . $pathSeparator;
        if (file_exists($fromdir . $attachment->fileName) or $attachment->type=='link') {
          $attachment->id=null;
          $attachment->refType=get_class($newObj);
          $attachment->refId=$newObj->id;
          $attachment->save();
          if ($attachment->type=='file') {
            $todir=$attachmentDirectory . $pathSeparator . "attachment_" . $attachment->id . $pathSeparator;
            if (!file_exists($todir)) {
              mkdir($todir, 0777, true);
            }
            copy($fromdir . $attachment->fileName, $todir . $attachment->fileName);
            $attachment->subDirectory=pq_str_replace($attachmentDirectory, '${attachmentDirectory}', $todir);
            $attachment->save();
          }
        }
      }
    }
    if (getLastOperationStatus($result)=='OK' and $withAssignments and property_exists($this, "_Assignment") and property_exists($newObj, "_Assignment")) {
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array(
          'idProfile'=>getSessionUser()->getProfile($this),
          'scope'=>'assignmentEdit'));
      if ($habil and $habil->rightAccess==1) {
        $ass=new Assignment();
        // First delete existing Assignment (possibly created from Responsible)
        if (property_exists($this, 'idResource') and $this->idResource) {
          $crit=array('idResource'=>$this->idResource, 'refType'=>get_class($this), 'refId'=>$newObj->id);
          $assResp=SqlElement::getSingleSqlElementFromCriteria('Assignment', $crit);
          if ($assResp and $assResp->id) {
            $resDel=$assResp->delete();
          }
        }
        $crit=array('refType'=>get_class($this), 'refId'=>$this->id);
        $lstAss=$ass->getSqlElementsFromCriteria($crit);
        foreach ($lstAss as $ass) {
          $res=new ResourceAll($ass->idResource);
          if ($res->idle) continue;
          if ($ass->supportedResource) continue; // Do not copy support assignment, will be generated automatically
          $oldAssId=$ass->id;
          $ass->id=null;
          $ass->idProject=$newObj->idProject;
          $ass->refType=$newClass;
          $ass->refId=$newObj->id;
          $ass->comment=null;
          $ass->realWork=0;
          $planningName=get_class($this) . 'PlanningElement';
          if ($this->$planningName->idPlanningMode) {
            $planningMode=new PlanningMode($this->$planningName->idPlanningMode);
          }
          if ($planningMode and $planningMode->code=='MAN') {
            $ass->assignedWork=null;
            $ass->leftWork=null;
            $ass->plannedWork=null;
          } else {
            $ass->leftWork=$ass->assignedWork;
            $ass->plannedWork=$ass->assignedWork;
          }
          $ass->realStartDate=null;
          $ass->realEndDate=null;
          $ass->plannedStartDate=null;
          $ass->plannedEndDate=null;
          $ass->realCost=0;
          $ass->leftCost=$ass->assignedCost;
          $ass->plannedCost=$ass->assignedCost;
          $ass->billedWork=null;
          $ass->idle=0;
          $resSaveAss=$ass->save();
          // Also copy AssignmentRecurring for recurring tasks
          $assRec=new AssignmentRecurring();
          $critRec=array('idAssignment'=>$oldAssId);
          $lstAssRec=$assRec->getSqlElementsFromCriteria($critRec);
          foreach ($lstAssRec as $assRec) {
            $assRec->id=null;
            $assRec->idAssignment=$ass->id;
            $assRec->refType=$newClass;
            $assRec->refId=$newObj->id;
            $resAssRec=$assRec->save();
          }
          // Also copy AssignmentSelection for recurring tasks
          $assSel=new AssignmentSelection();
          $critSel=array('idAssignment'=>$oldAssId);
          $lstAssSel=$assSel->getSqlElementsFromCriteria($critSel);
          foreach ($lstAssSel as $assSel) {
            $assSel->id=null;
            $assSel->idAssignment=$ass->id;
            $assSel->startDate=null;
            $assSel->endDate=null;
            $assSel->userSelected=0;
            $assSel->selected=0;
            $resAssSel=$assSel->save();
          }
        }
      }
    }
    if (getLastOperationStatus($result)=='OK' and $copyToWithSubTask and property_exists($this, '_SubTask') and property_exists($newObj, "_SubTask")) {
      $subTask=new SubTask();
      $lstSub=$subTask->getSqlElementsFromCriteria(array("refType"=>get_class($this), "refId"=>$this->id));
      foreach ($lstSub as $subT) {
        $subT->id=null;
        $subT->refType=get_class($newObj);
        $subT->refId=$newObj->id;
        $subT->idProject=$newProject;
        $subT->done=0;
        $subT->idle=0;
        $subT->handled=0;
        $subT->save();
      }
    }
    if (getLastOperationStatus($result)=='OK' and property_exists($this, '_BillLine') and property_exists($newObj, '_BillLine')) { // Copy BillLines
      $crit=array('refType'=>get_class($this), 'refId'=>$this->id);
      $line=new BillLine();
      $lines=$line->getSqlElementsFromCriteria($crit);
      foreach ($lines as $line) {
        $line->id=null;
        $line->refType=get_class($newObj);
        $line->refId=$newObj->id;
        $line->save();
      }
    }
    $newObj->_copyResult=$returnValue;
    return $newObj;
  }

  // ============================================================================**********
  // GET AND FETCH OBJECTS FUNCTIONS
  // ============================================================================**********

  /**
   * =========================================================================
   * Retrieve an object from the Request (modified Form) - Public method
   *
   * @return void (operate directly on the object)
   */
  public function fillFromRequest($ext=null) {
    $this->fillSqlElementFromRequest(null, $ext);
  }

  /**
   * ========================================================================
   * Retrieve a list of objects from the Database
   * Called from an empty object of the expected class
   *
   * @param array $critArray
   *          the critera as an array
   * @param boolean $initializeIfEmpty
   *          indicating if no result returns an
   *          initialised element or not
   * @param string $clauseWhere
   *          Sql Where clause (alternative way to define criteria)
   *          => $critArray must not be set
   * @param string $clauseOrderBy
   *          Sql Order By clause
   * @param boolean $getIdInKey
   * @return SqlElement[] an array of objects
   */
  public function getSqlElementsFromCriteria($critArray, $initializeIfEmpty=false, $clauseWhere=null, $clauseOrderBy=null, $getIdInKey=false, $withoutDependentObjects=false, $maxElements=null) {
    if (is_array($clauseWhere)) {
      errorLog("Error : Call getSqlElementsFromCriteria() with clauseWhere as Array");
      errorLog($clauseWhere);
      debugPrintTraceStack();
      if (!$critArray) {
        $critArray=$clauseWhere;
      }
      $clauseWhere=null;
    }
    // scriptLog("getSqlElementsFromCriteria(implode('|',$critArray), $initializeIfEmpty,$clauseWhere, $clauseOrderBy, $getIdInKey)");
    // Build where clause from criteria
    global $globalSilentErrors;
    if ($clauseWhere) $clauseWhere=pq_str_replace(array(' in ()', ' IN ()'), array(' in (0)', ' IN (0)'), $clauseWhere); // Should not be mandatory, but will avoid several coding issue
    $whereClause='';
    $objects=array();
    $className=get_class($this);
    $defaultObj=new $className();
    if ($critArray) {
      foreach ($critArray as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        if ($valCrit==null or $valCrit==' ') {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . ' is null';
        } else {
          if ($this->getDataType($colCrit)=='int' and is_numeric($valCrit)) {
            $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '=' . $valCrit;
          } else {
            $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '=' . Sql::str($valCrit);
          }
        }
        $defaultObj->$colCrit=$valCrit;
      }
    } else if ($clauseWhere) {
      $whereClause=' where ' . $clauseWhere;
    }
    $objectCrit=$this->getDatabaseCriteria();
    if (count($objectCrit)>0) {
      foreach ($objectCrit as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . " = " . Sql::str($valCrit) . " ";
      }
    }
    if (property_exists($this, 'isPrivate')) {
      $whereClause.=($whereClause=='')?' where ':' and ';
      $whereClause.=SqlElement::getPrivacyClause($this);
    }
    if (pq_array_key_exists($className, self::$_cachedQuery)) {
      if (pq_array_key_exists($whereClause, self::$_cachedQuery[$className])) {
        return self::$_cachedQuery[$className][$whereClause];
      }
    }
    // If $whereClause is set, get the element from Database
    $query='select * from ' . $this->getDatabaseTableName() . $whereClause;
    if ($clauseOrderBy) {
      $query.=' order by ' . $clauseOrderBy;
    } else if (isset($this->sortOrder)) {
      $query.=' order by ' . $this->getDatabaseTableName() . '.sortOrder';
    }
    if ($maxElements) {
      $query.=' LIMIT ' . $maxElements;
    }
    $result=Sql::query($query);

    if (Sql::$lastQueryNbRows>0) {
      $line=Sql::fetchLine($result);
      while ($line) {
        $obj=clone ($this);
        // get all data fetched
        $keyId=null;
        foreach ($obj as $col_name=>$col_value) {
          if (pq_substr($col_name, 0, 1)=="_") {
            // not a field, just for presentation purpose
          } else if ($this->isAttributeSetToField($col_name, 'calculated')) {
            // calculated field : not to be fetched
          } else if (pq_ucfirst($col_name)==$col_name) {
            if (!$withoutDependentObjects) {
              $obj->$col_name=$obj->getDependantSqlElement($col_name);
            }
          } else {
            $dbColName=$obj->getDatabaseColumnName($col_name);
            if (pq_array_key_exists($dbColName, $line)) {
              $obj->{$col_name}=$line[$dbColName];
            } else if (pq_array_key_exists(pq_strtolower($dbColName), $line)) {
              $obj->{$col_name}=$line[pq_strtolower($dbColName)];
            } else {
              if (!$globalSilentErrors) errorLog("Error on SqlElement to get '" . $col_name . "' for Class '" . get_class($obj) . "' " . " : field '" . $dbColName . "' not found in Database.");
            }
            if ($col_name=='id' and $getIdInKey) {
              $keyId='#' . $obj->{$col_name};
            }
          }
          // FOR PHP 7.1 COMPATIBILITY
          $dataType=$obj->getDataType($col_name);
          $dataLength=$obj->getDataLength($col_name);
          if ($obj->{$col_name}===null and (($dataType=='decimal') or ($dataType=='numeric')) and $col_name!='warningValue' and $col_name!='alertValue' and 
          // ELIOTT - LEAVE SYSTEM
          !(in_array(get_class($obj), self::$_classesArrayToBypassPHPCompatibilityIf) and in_array($col_name, self::$_attributesArrayToBypassPHPCompatibilityIf))) {
            // ELIOTT - LEAVE SYSTEM
            $obj->{$col_name}=0;
          }
        }
        if ($getIdInKey) {
          $objects[$keyId]=$obj;
        } else {
          $objects[]=$obj;
        }
        if (pq_array_key_exists($className, self::$_cachedQuery)) {
          $whereClauseSingle='#id=' . $obj->id;
          self::$_cachedQuery[$className][$whereClauseSingle]=$obj;
        }
        $line=Sql::fetchLine($result);
      }
    } else {
      if ($initializeIfEmpty) {
        $objects[]=$defaultObj; // return at least 1 element, initialized with criteria
      }
    }
    if (pq_array_key_exists($className, self::$_cachedQuery)) {
      self::$_cachedQuery[$className][$whereClause]=$objects;
    }
    return $objects;
  }

  /**
   * ========================================================================
   * Retrieve the count of a list of objects from the Database
   * Called from an empty object of the expected class
   *
   * @param $critArray Array
   *          the critera asd an array
   * @param $clauseWhere String
   *          Sql Where clause (alternative way to define criteria) => $critArray must not be set
   * @param $clauseOrderBy String
   *          Sql Order By clause
   * @return Array an array of objects
   */
  public function countSqlElementsFromCriteria($critArray, $clauseWhere=null) {
    // Build where clause from criteria
    $whereClause='';
    $objects=array();
    $className=get_class($this);
    $defaultObj=new $className();
    if ($critArray) {
      foreach ($critArray as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        if ($valCrit==null) {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . ' is null';
        } else {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '= ' . Sql::str($valCrit);
        }
        $defaultObj->$colCrit=$valCrit;
      }
    } else if ($clauseWhere) {
      $whereClause=' where ' . $clauseWhere;
    }
    // If $whereClause is set, get the element from Database
    $query="select count(*) as cpt from " . $this->getDatabaseTableName() . $whereClause;
    $result=Sql::query($query);
    if (Sql::$lastQueryNbRows>0) {
      $line=Sql::fetchLine($result);
      return $line['cpt'];
    }
    return 0;
  }

  public function getMaxValueFromCriteria($field, $critArray, $clauseWhere=null) {
    $whereClause='';
    $objects=array();
    $className=get_class($this);
    $defaultObj=new $className();
    if ($critArray) {
      foreach ($critArray as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        if ($valCrit==null) {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . ' is null';
        } else {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '= ' . Sql::str($valCrit);
        }
        $defaultObj->$colCrit=$valCrit;
      }
    } else if ($clauseWhere) {
      $whereClause=' where ' . $clauseWhere;
    }
    // If $whereClause is set, get the element from Database
    $query="select max($field) as value from " . $this->getDatabaseTableName() . $whereClause;
    $result=Sql::query($query);
    if (Sql::$lastQueryNbRows>0) {
      $line=Sql::fetchLine($result);
      return $line['value'];
    }
    return null;
  }

  public function getMinValueFromCriteria($field, $critArray, $clauseWhere=null, $excludeNull=false) {
    $whereClause='';
    $objects=array();
    $className=get_class($this);
    $defaultObj=new $className();
    if ($critArray) {
      foreach ($critArray as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        if ($valCrit==null) {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . ' is null';
        } else {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '= ' . Sql::str($valCrit);
        }
        $defaultObj->$colCrit=$valCrit;
      }
    } else if ($clauseWhere) {
      $whereClause=' where ' . $clauseWhere;
    }
    if ($excludeNull) {
      $whereClause.=" and $field is not null";
    }
    // If $whereClause is set, get the element from Database
    $query="select min($field) as value from " . $this->getDatabaseTableName() . $whereClause;
    $result=Sql::query($query);
    if (Sql::$lastQueryNbRows>0) {
      $line=Sql::fetchLine($result);
      return $line['value'];
    }
    return null;
  }

  public function sumSqlElementsFromCriteria($field, $critArray, $clauseWhere=null, $grouped=null) {
    // Build where clause from criteria
    $fields=array();
    if (is_array($field)) {
      $fields=$field;
    } else {
      $fields=array($field);
    }
    $whereClause='';
    $objects=array();
    $className=get_class($this);
    $defaultObj=new $className();
    if ($critArray) {
      foreach ($critArray as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        if ($valCrit==null) {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . ' is null';
        } else {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '= ' . Sql::str($valCrit);
        }
        $defaultObj->$colCrit=$valCrit;
      }
    } else if ($clauseWhere) {
      $whereClause=' where ' . $clauseWhere;
    }
    // If $whereClause is set, get the element from Database
    $selectFields="";
    foreach ($fields as $fld) {
      if ($selectFields) $selectFields.=', ';
      $fldName=$defaultObj->getDatabaseColumnName($fld);
      $selectFields.=" sum($fldName) as sum" . pq_strtolower($fld);
    }

    $query="select " . $selectFields . (($grouped)?',' . $grouped:'') . ' from ' . $this->getDatabaseTableName() . $whereClause . (($grouped)?' group by ' . $grouped:'');
    $result=Sql::query($query);
    if (Sql::$lastQueryNbRows>0) {
      $line=Sql::fetchLine($result);
      if ($grouped) {
        $res=array();
        while ($line) {
          $resLine=array();
          foreach ($line as $key=>$val) {
            $resLine[pq_strtolower($key)]=$val;
          }
          $res[]=$resLine;
          $line=Sql::fetchLine($result);
        }
        return $res;
      } else if (is_array($field)) {
        return $line;
      } else {
        return $line["sum" . pq_strtolower($field)];
      }
    }
    return null;
  }

  public function countGroupedSqlElementsFromCriteria($critArray, $critGroup, $critwhere) {
    // Build where clause from criteria
    $whereClause='';
    $className=get_class($this);
    if ($critArray) {
      foreach ($critArray as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' ':' and ';
        if ($valCrit==null) {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . ' is null';
        } else {
          $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . '= ' . Sql::str($valCrit);
        }
      }
    } else {
      $whereClause=$critwhere;
    }
    $objectCrit=$this->getDatabaseCriteria();
    if (count($objectCrit)>0) {
      foreach ($objectCrit as $colCrit=>$valCrit) {
        $whereClause.=($whereClause=='')?' where ':' and ';
        $whereClause.=$this->getDatabaseTableName() . '.' . $this->getDatabaseColumnName($colCrit) . " = " . Sql::str($valCrit) . " ";
      }
    }

    $groupList='';
    $critGroup=array_map('pq_strtolower', $critGroup);
    foreach ($critGroup as $group) {
      $groupList.=($groupList=='')?'':', ';
      $groupList.=$group;
    }
    $query="select $groupList, count(*) as cpt from " . $this->getDatabaseTableName() . ' where ' . $whereClause . " group by $groupList";
    $result=Sql::query($query);
    $groupRes=array();
    if (Sql::$lastQueryNbRows>0) {
      while ($line=Sql::fetchLine($result)) {
        $grp='';
        foreach ($critGroup as $group) {
          $grp.=(($grp=='')?'':'|') . $line[$group];
        }
        $groupRes[$grp]=$line['cpt'];
      }
    }
    return $groupRes;
  }

  // BEGIN - ADD BY TABARY - GET FIRST OBJECT FROM SELECT
  /**
   * ==========================================================================
   * Retrieve the first object from the Database
   * Called from an empty object of the expected class
   *
   * @param string $class
   *          The object class
   * @param array $critArray
   *          the critera as an array
   * @return object : The object find - If not found set attribut _singleElementNotFound
   */
  public static function getFirstSqlElementFromCriteria($class, $critArray) {
    $obj=new $class();
    if ($class=='Attachment') {
      if (pq_array_key_exists('refType', $critArray)) {
        if ($critArray['refType']=='User' or $critArray['refType']=='Contact') {
          $critArray['refType']='Resource';
        }
      }
    }
    $objList=$obj->getSqlElementsFromCriteria($critArray, true);
    if (count($objList)==0) {
      $obj->_singleElementNotFound=true;
      return $obj;
    } else {
      return $objList[0];
    }
  }

  // END - ADD BY TABARY - GET FIRST OBJECT FROM SELECT

  /**
   * ==========================================================================
   * Retrieve a single object from the Database
   * Called from an empty object of the expected class
   *
   * @param $critArray Array
   *          the critera asd an array
   * @param $initializeIfEmpty boolean
   *          indicating if no result returns en initialised element or not
   * @return Array an array of objects
   */
  public static function getSingleSqlElementFromCriteria($class, $critArray, $withoutDepedentElements=false) {
    $obj=new $class();
    if ($class=='Attachment') {
      if (pq_array_key_exists('refType', $critArray)) {
        if ($critArray['refType']=='User' or $critArray['refType']=='Contact') {
          $critArray['refType']='Resource';
        }
      }
    }
    $objList=$obj->getSqlElementsFromCriteria($critArray, true, null, null, null, $withoutDepedentElements);
    if (count($objList)==1) {
      return $objList[0];
    } else {
      $obj->_singleElementNotFound=true;
      if (count($objList)>1) {
        // traceLog("getSingleSqlElementFromCriteria for object '" . $class . "' returned more than 1 element");
        $obj->_tooManyRows=true;
      }
      return $obj;
    }
  }

  /**
   * ==========================================================================
   * Retrieve an object from the Request (modified Form)
   *
   * @return void (operate directly on the object)
   */
  private function fillSqlElementFromRequest($included=false, $ext=null) {
    foreach ($this as $key=>$value) {
      // If property is an object, recusively fill it
      if (pq_ucfirst($key)==$key and pq_substr($key, 0, 1)!="_") {
        if (is_object($key)) {
          $subObjectClass=get_class($key);
          $subObject=$key;
        } else {
          $subObjectClass=$key;
          $subObject=new $subObjectClass();
        }
        $subObject->fillSqlElementFromRequest(true, $ext);
        $this->$key=$subObject;
      } else {
        if (pq_substr($key, 0, 1)=="_") {
          // not a real field
        } else {
          $dataType=$this->getDataType($key);
          $dataLength=$this->getDataLength($key);
          $formField=$key . $ext;
          if ($included) { // if included, then object is called recursively, name is prefixed by className
            $formField=get_class($this) . '_' . $key . $ext;
          }
          if ($dataType=='int') {
            if ($dataLength==1 and pq_substr($key, 0, 11)!='periodicity') {
              if (pq_array_key_exists($formField, $_REQUEST)) {
                // if field is hidden, must check value, otherwise just check existence
                // if ($this->isAttributeSetToField($key, 'hidden')) {
                // V5.4 : for action isPrivate can be dynamically hidden, was not detected with prior test
                if ($_REQUEST[$formField]==='0' or $_REQUEST[$formField]==='1') {
                  $this->$key=$_REQUEST[$formField];
                } else if ($_REQUEST[$formField]=='') {
                  $this->$key=0;
                } else {
                  $this->$key=1;
                }
              } else {
                // echo "val=False<br/>";
                $this->$key=0;
              }
            } else if (pq_array_key_exists($formField, $_REQUEST)) {
              $this->$key=Security::checkValidInteger($_REQUEST[$formField]);
            }
          } else if ($dataType=='datetime') {
            $formFieldBis=$key . "Bis" . $ext;
            if ($included) {
              $formFieldBis=get_class($this) . '_' . $key . "Bis" . $ext;
            }
            if (isset($_REQUEST[$formFieldBis])) {
              $test=Security::checkValidDateTime($_REQUEST[$formField]);
              $test=Security::checkValidDateTime($_REQUEST[$formFieldBis]);
              $this->$key=$_REQUEST[$formField] . " ";
              if (pq_substr($_REQUEST[$formFieldBis], 0, 1)=='T') {
                $this->$key.=pq_substr($_REQUEST[$formFieldBis], 1);
              } else {
                $this->$key.=$_REQUEST[$formFieldBis];
              }
            } else {
              // hidden field
              if (isset($_REQUEST[$formField])) {
                $this->$key=$_REQUEST[$formField];
              }
            }
            if ($this->$key) $this->$key=convertUserTimeToServerTimezone($this->$key);
          } else if ($dataType=='decimal' and (pq_substr($key, -4, 4)=='Work')) {
            if (pq_array_key_exists($formField, $_REQUEST)) {
              if (get_class($this)=='WorkElement' or get_class($this)=='TokenDefinition' or get_class($this)=='Resource') {
                $this->$key=Work::convertImputation($_REQUEST[$formField]);
              } else {
                $this->$key=Work::convertWork($_REQUEST[$formField]);
              }
            }
          } else if ($dataType=='time') {
            if (pq_array_key_exists($formField, $_REQUEST)) {
              $test=Security::checkValidDateTime($_REQUEST[$formField]);
              $this->$key=pq_substr($_REQUEST[$formField], 1);
              if ($this->$key) $this->$key=convertUserTimeToServerTimezone($this->$key);
            }
          } else if ($dataType=='date') {
            if (pq_array_key_exists($formField, $_REQUEST)) {
              $test=Security::checkValidDateTime($_REQUEST[$formField]);
              $this->$key=$_REQUEST[$formField];
            }
          } else if ($dataType=='varchar' or pq_substr($dataType, -4)=='text') {
            if (pq_array_key_exists($formField, $_REQUEST)) {
              //$this->$key=preg_replace('/[\xF0-\xF7].../s', '', pq_nvl($_REQUEST [$formField]));
              $this->$key=pq_nvl($_REQUEST [$formField]);
            }
          } else {
            if (pq_array_key_exists($formField, $_REQUEST)) {
              $this->$key=$_REQUEST[$formField];
            }
          }
          // FOR PHP 7.1 COMPATIBILITY
          if (($this->$key===null or $this->$key==='') and (($dataType=='decimal') or ($dataType=='numeric')) and $key!='warningValue' and $key!='alertValue' and 
          // ELIOTT - LEAVE SYSTEM
          !(in_array(get_class($this), self::$_classesArrayToBypassPHPCompatibilityIf) and in_array($key, self::$_attributesArrayToBypassPHPCompatibilityIf))) {
            // ELIOTT - LEAVE SYSTEM
            $this->$key=0;
          }
        }
      }
    }
    if (RequestHandler::isCodeSet('moveToAfterCreate')) {
      $this->_moveToAfterCreate=RequestHandler::getId('moveToAfterCreate');
    }
  }

  /**
   * ==========================================================================
   * Retrieve an object from the Database
   *
   * @return void
   */
  private function getSqlElement($withoutDependentObjects=false) {
    global $globalSilentErrors;
    $curId=$this->id;
    if (!pq_trim($curId)) {
      $curId=null;
    }

    // Cache management
    if ($curId and pq_array_key_exists(get_class($this), self::$_cachedQuery)) {
      $whereClause='#id=' . $curId;
      $class=get_class($this);
      if (pq_array_key_exists($whereClause, self::$_cachedQuery[$class])) {
        $obj=self::$_cachedQuery[$class][$whereClause];
        $peName=$class . 'PlanningElement';
        // PBER : if item in case is $withoutDependentObjects=true and current is $withoutDependentObjects=true, must fetch object
        if ($withoutDependentObjects or !property_exists($obj, $peName) or is_object($obj->$peName)) {
          foreach ($obj as $fld=>$val) {
            $this->$fld=$obj->$fld;
          }
          return;
        }
      }
    }
    $empty=true;
    // If id is set, get the element from Database
    if ($curId!=NULL) {
      $query="select * from " . $this->getDatabaseTableName() . ' where id=' . $curId;
      foreach ($this->getDatabaseCriteria() as $critFld=>$critVal) {
        $query.=' and ' . $critFld . ' = ' . Sql::str($critVal);
      }
      $result=Sql::query($query);
      if (Sql::$lastQueryNbRows>0) {
        $empty=false;
        $line=Sql::fetchLine($result);
        if (!is_array($line)) {
          global $globalCatchErrors;
          if ($globalCatchErrors==true) {
            Sql::$lastQueryErrorCode='999';
            Sql::$lastQueryErrorMessage="Error in getSqlElement() for " . get_class($this) . " #$this->id : no data retreived.";
            return $this;
          } else {
            errorLog("Error in getSqlElement() for " . get_class($this) . " #$this->id : no data retreived. Exiting script");
            exit();
          }
        }
        // get all data fetched
        foreach ($this as $col_name=>$col_value) {
          if (pq_substr($col_name, 0, 1)=="_") {
            $colName=pq_substr($col_name, 1);
            if (is_array($this->{$col_name}) and pq_ucfirst($colName)==$colName and !$withoutDependentObjects) {
              if (pq_substr($colName, 0, 4)=="Link") {
                $linkClass=null;
                if (pq_strlen($colName)>4) {
                  $linkClass=pq_substr($colName, 5);
                }
                $this->{$col_name}=Link::getLinksForObject($this, $linkClass);
              } else if ($colName=="ResourceCost") {
                $this->{$col_name}=$this->getResourceCost();
              } else if ($colName=="VersionProject") {
                if (get_class($this)!='OriginalVersion' and get_class($this)!='TargetVersion' and get_class($this)!='OriginalProductVersion' and get_class($this)!='TargetProductVersion' and get_class($this)!='OriginalComponentVersion' and get_class($this)!='TargetComponentVersion') {
                  $vp=new VersionProject();
                  $idCrit='id' . ((get_class($this)=='Project')?'Project':'Version');
                  $crit=array($idCrit=>$this->id);
                  $this->{$col_name}=$vp->getSqlElementsFromCriteria($crit, false);
                }
              } else if ($colName=="DocumentVersion") {
                $dv=new DocumentVersion();
                $crit=array('idDocument'=>$this->id);
                $this->{$col_name}=$dv->getSqlElementsFromCriteria($crit, false);
              } else if ($colName=="ExpenseDetail") {
                $this->{$col_name}=$this->getExpenseDetail();
              } else if (pq_substr($colName, 0, 10)=="Dependency") {
                $depType=null;
                $crit=Array();
                if (pq_strlen($colName)>10) {
                  $depType=pq_substr($colName, 11);
                  if ($depType=="Successor") {
                    $crit=Array("PredecessorRefType"=>get_class($this), "PredecessorRefId"=>$this->id);
                  } else {
                    $crit=Array("SuccessorRefType"=>get_class($this), "SuccessorRefId"=>$this->id);
                  }
                }
                $dep=new Dependency();
                $this->{$col_name}=$dep->getSqlElementsFromCriteria($crit, false);
              } else {
                if (!$withoutDependentObjects and pq_substr(get_class($this), -4)!='Main') {
                  $this->{$col_name}=$this->getDependantSqlElements($colName);
                }
              }
            }
          } else if (pq_ucfirst($col_name)==$col_name) {
            if (!$withoutDependentObjects) {
              $this->{$col_name}=$this->getDependantSqlElement($col_name);
            }
          } else if (pq_strpos($this->getFieldAttributes($col_name), 'calculated')!==false) {
            // calculated
          } else {
            // $test=$line[$this->getDatabaseColumnName($col_name)];
            $dbColName=$this->getDatabaseColumnName($col_name);
            $dbType=$this->getDataType($col_name);
            $dbLength=$this->getDataLength($col_name);
            if (pq_array_key_exists($dbColName, $line)) {
              $this->{$col_name}=$line[$dbColName];
            } else if (pq_array_key_exists(pq_strtolower($dbColName), $line)) {
              $dbColName=pq_strtolower($dbColName);
              $this->{$col_name}=$line[$dbColName];
            } else {
              if (!$globalSilentErrors) errorLog("Error on SqlElement to get '" . $col_name . "' for Class '" . get_class($this) . "' " . " : field '" . $dbColName . "' not found in Database on table " . $this->getDatabaseTableName());
            }
            // FOR PHP 7.1 COMPATIBILITY
            // if ($this->{$col_name}===null // FOR TEST PURPOSE
            if ($this->{$col_name}==='' and (($dbType=='numeric') or ($dbType=='decimal')) and $col_name!='warningValue' and $col_name!='alertValue' and 
            // ELIOTT - LEAVE SYSTEM
            !(in_array(get_class($this), self::$_classesArrayToBypassPHPCompatibilityIf) and in_array($col_name, self::$_attributesArrayToBypassPHPCompatibilityIf))) {
              // ELIOTT - LEAVE SYSTEM
              $this->{$col_name}=0;
            }
          }
        }
      } else {
        $this->id=null;
      }
    }
    if ($empty and !$withoutDependentObjects) {
      // Get all the elements that are objects (first letter is uppercase in object properties)
      foreach ($this as $key=>$value) {
        // echo pq_substr($key,0,1) . "<br/>";
        if (pq_ucfirst($key)==$key and pq_substr($key, 0, 1)!="_") {
          $this->{$key}=$this->getDependantSqlElement($key);
        }
      }
    }
    // set default idUser if exists
    if ($empty and property_exists($this, 'idUser') and get_class($this)!='Affectation' and get_class($this)!='Message' and get_class($this)!='VotingAttribution') {
      if (sessionUserExists()) {
        $this->idUser=getSessionUser()->id;
      }
    }
    if ($curId and pq_array_key_exists(get_class($this), self::$_cachedQuery)) {
      $whereClause='#id=' . $curId;
      $class=get_class($this);
      self::$_cachedQuery[get_class($this)][$whereClause]=clone ($this);
    }
  }

  /**
   * ==========================================================================
   * retrieve single object included in an object from the Database
   *
   * @param $objClass String
   *          the name of the class of the included object
   * @return Object an object
   */
  private function getDependantSqlElement($objClass) {
    $curId=$this->id;
    if (!pq_trim($curId)) {
      $curId=null;
    }
    $obj=new $objClass(null, true);
    $obj->refId=$this->id;
    $obj->refType=get_class($this);
    // gautier Vote
    if ($obj->refType=='TicketSimple' and $objClass=='VotingItem') $obj->refType='Ticket';
    if (pq_substr($obj->refType, -4)=='Main') $obj->refType=pq_substr($obj->refType, 0, -4);
    // If id is set, get the elements from Database
    if (($curId!=null) and ($obj instanceof SqlElement)) {
      $obj->getSqlElement(true);
      // set the reference data
      // build query
      $query="select id from " . $obj->getDatabaseTableName() . ' where refId =' . $curId . " and refType ='" . $obj->refType . "'";
      foreach ($obj->getDatabaseCriteria() as $critFld=>$critVal) {
        $query.=' and ' . $critFld . ' = ' . Sql::str($critVal);
      }
      $result=Sql::query($query);
      // if no element in database, will return empty object
      //
      // IMPROVEMENT ON V4.2.0 : attention, this may return results when it did not previously...
      if (Sql::$lastQueryNbRows>0) {
        $line=Sql::fetchLine($result);
        // get all data fetched for the dependant element
        $obj->id=$line['id'];
        $obj->getSqlElement();
      }
    }
    // set the dependant element
    return $obj;
  }

  /**
   * ==========================================================================
   * retrieve objects included in an object from the Database
   *
   * @param $objClass String
   *          the name of the class of the included object
   * @return Array an array ob objects
   */
  private function getDependantSqlElements($objClass) {
    if (get_class($this)=='Organization' and $objClass=='Resource') $objClass='ResourceAll';
    $curId=$this->id;
    $obj=new $objClass();
    $list=array();
    // $obj->refId=$this->id;
    // $obj->refType=get_class($this);
    // If id is set, get the elements from Database
    if (($curId!=NULL) and ($obj instanceof SqlElement)) {
      // set the reference data
      // build query
      $query="select id from " . $obj->getDatabaseTableName();
      if (property_exists($objClass, 'id' . get_class($this)) and $objClass!='Note' and $objClass!='Attachment' and $objClass!='Link') {
        $query.=" where " . $obj->getDatabaseColumnName('id' . get_class($this)) . "= " . Sql::fmtId($curId) . " ";
      } else {
        $refType=get_class($this);
        if ($refType=='TicketSimple') {
          $refType='Ticket';
        }
        $query.=" where refType ='$refType' and refId=" . Sql::fmtId($curId);
      }
      $query.=" order by id desc ";
      $result=Sql::query($query);
      // if no element in database, will return empty array
      if (Sql::$lastQueryNbRows>0) {
        while ($line=Sql::fetchLine($result)) {
          $newObj=new $objClass();
          $newObj->id=$line['id'];
          $newObj->getSqlElement();
          $list[]=$newObj;
        }
      }
    }
    // set the dependant element
    return $list;
  }

  // ============================================================================**********
  // GET STATIC DATA FUNCTIONS
  // ============================================================================**********

  /**
   * ========================================================================
   * return the type of a column depending on its name
   *
   * @param $colName String
   *          the name of the column
   * @return String the type of the data
   */
  public function getDataType($colName) {
    $colName=pq_strtolower($colName);
    $formatList=self::getFormatList(get_class($this));
    if (!pq_array_key_exists($colName, $formatList)) {
      foreach ($this as $col=>$val) {
        if (is_object($val)) {
          $subObj=new $col();
          $subType=$subObj->getDataType($colName);
          if ($subType!='undefined') {
            return $subType;
          }
        }
      }
      return 'undefined';
    }
    $fmt=$formatList[$colName];
    $split=preg_split('/[()\s]+/', pq_nvl($fmt), 2);
    return $split[0];
  }

  /**
   * ========================================================================
   * return the length (max) of a column depending on its name
   *
   * @param $colName String
   *          the name of the column
   * @return String the type of the data
   */
  public function getDataLength($colName) {
    $colName=pq_strtolower($colName);
    $formatList=self::getFormatList(get_class($this));
    if (!pq_array_key_exists($colName, $formatList)) {
      return 0;
    }
    $fmt=$formatList[$colName];
    $split=preg_split('/[()\s]+/', pq_nvl($fmt), 3);
    $type=$split[0];
    if ($type=='date') {
      return 10;
    } else if ($type=='time') {
      return 5;
    } else if ($type=='timestamp' or $type=='datetime') {
      return 19;
    } else if ($type=='double') {
      return 2;
    } else if ($type=='text') {
      return 65535;
    } else if ($type=='mediumtext') {
      return 16777215;
    } else if ($type=='longtext') {
      return 4294967295;
    } else {
      if (count($split)>=2) {
        return ($split[1]);
      } else {
        return 0;
      }
    }
  }

  /**
   * ========================================================================
   * return the generic layout for grit list
   *
   * @return String the layout from static data
   */
  public function getLayout($idLayout=null, $isReport=false) {
    $result="";
    $columns=ColumnSelector::getColumnsList(get_class($this));
    if ($idLayout) {
      $columns=LayoutColumnSelector::getColumnsList(get_class($this), $idLayout, $isReport);
    }
    $totWidth=0;
    foreach ($columns as $col) {
      if ($col->hidden) {
        continue;
      }
      if (!$isReport and !self::isVisibleField($col->attribute)) {
        continue;
      }
      if ($col->formatter=='numericFormatter' and $col->field=='id') $col->formatter='idFormatter';
      if ($col->attribute=='hatchPattern') $col->formatter='hatchPatternFormatter';
      $result.='<th';
      $result.=' field="' . htmlEncode($col->field) . '"';
      $result.=' width="' . (($col->field=='name')?'auto':$col->widthPct . '%') . '"';
      $result.=($col->formatter)?' formatter="' . htmlEncode($col->formatter) . '"':'';
      $result.=($col->_from)?' from="' . $col->_from . '"':'';
      $result.=($col->hidden and $col->field!='id')?' hidden="true"':'';
      $result.='>' . $col->_displayName . '</th>' . "\n";
      $totWidth+=($col->field=='name')?0:$col->widthPct;
    }
    if ($totWidth<90) {
      $autoWidth=100-$totWidth;
    } else {
      $autoWidth=10;
    }
    $result=pq_str_replace('width="auto"', 'width="' . $autoWidth . '%"', $result);
    return $result;
  }

  // ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
  /**
   * ========================================================================
   * return the spinner attributes (min, max, step) for a given field
   *
   * @return string
   */
  public function getSpinnerAttributes($fieldName) {
    $spinnersAttributes=$this->getStaticSpinnersAttributes();
    if (pq_array_key_exists($fieldName, $spinnersAttributes)) {
      return $spinnersAttributes[$fieldName];
    } else {
      return '';
    }
  }

  // END ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER

  // ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
  /**
   * ========================================================================
   * return the array of fields to disabled on form change
   *
   * @return '' or a string structured like js array
   */
  public function getDisabledFieldsOnChange() {
    $disabledFieldsOnChange=$this->getStaticDisabledFieldsOnChange();
    $theString='';
    // The main object
    if ($disabledFieldsOnChange!==null and is_array($disabledFieldsOnChange) and count($disabledFieldsOnChange)>0) {
      $theClass=get_class($this);
      foreach ($disabledFieldsOnChange as $disabledFieldOnChange) {
        $theString.='"' . $theClass . $disabledFieldOnChange . '",';
      }
    }
    // The sub-objects
    foreach ($this as $field=>$val) {
      if (is_object($val) and pq_substr($field, 0, 1)!='_') {
        $disabledFieldsOnChange=$val->getStaticDisabledFieldsOnChange();
        if ($disabledFieldsOnChange!==null and is_array($disabledFieldsOnChange) and count($disabledFieldsOnChange)>0) {
          $theClass=get_class($val);
          foreach ($disabledFieldsOnChange as $disabledFieldOnChange) {
            // Special for '_spe_' : Because the id Dom is construct by hand, it's simplier like this
            if (pq_substr($disabledFieldOnChange, 0, 5)==='_spe_') {
              $theString.='"_' . $disabledFieldOnChange . '",';
            } else {
              $theString.='"' . $theClass . '_' . $disabledFieldOnChange . '",';
            }
          }
        }
      }
    }

    if ($theString!='') {
      $theString='[' . pq_substr($theString, 0, -1) . ']';
    }
    return $theString;
  }

  // END ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET

  // BEGIN - ADD BY TABARY - TOOLTIP
  /**
   * ========================================================================
   * return the tooltip of a given field.
   *
   * @return array of fields with tooltip
   */
  public function getFieldTooltip($fieldName) {
    $fieldsTooltip=$this->getStaticFieldsTooltip();
    if (pq_array_key_exists($fieldName, $fieldsTooltip)) {
      return $fieldsTooltip[$fieldName];
    } else {
      return '';
    }
  }

  // END - ADD BY TABARY - TOOLTIP

  /**
   * ========================================================================
   * return the generic attributes (required, disabled, .
   *
   * ..) for a given field
   *
   * @return Array an array of fields with specific attributes
   */
  public function getFieldAttributes($fieldName) {
    $globalHasLocal=false;
    $isLocalField=false;
    if (pq_substr($fieldName, -5)=='Local') {
      if (!property_exists($this, 'idProject') or !$this->hasCurrency()) {
        if (self::isPct($fieldName) or self::isWork($fieldName) or self::isDate($fieldName)) return 'hidden,calculated';
        else return 'hidden';
      }
      if (!self::isPct($fieldName) and !self::isWork($fieldName) and !self::isDate($fieldName) and pq_substr($fieldName, 0, 7)!='_label_' and $this->id) {
        $isLocalField=true;
        $fieldName=pq_substr($fieldName, 0, -5);
      }
    } else {
      if (self::isAmount($fieldName)) {
        if (property_exists($this, $fieldName . 'Local')) {
          $globalHasLocal=true;
        }
      }
    }
    $fieldsAttributes=$this->getStaticFieldsAttributes();
    if (pq_array_key_exists($fieldName, $fieldsAttributes)) {
      $result=$fieldsAttributes[$fieldName];
    } else {
      $result='';
    }
    if ($globalHasLocal and property_exists($this, 'idProject') and $this->hasCurrency()) {
      $result=pq_str_replace('required', '', $result);
      $result.=($this->showGlobalCurrency())?',readonly':',hidden';
    } // else if ($isLocalField and strpos($result,'required')!==false) {
      // $old=$this->getOld(true);
      // if (!$this->idProject or ! $old->hasCurrency()) $result=pq_str_replace('required','',$result);
      // if (!$this->idProject) $result=pq_str_replace('required','',$result);
      // }
    return $result;
  }

  public function isAttributeSetToField($fieldName, $attribute) {
    if (pq_substr($fieldName, -5)=='Local') {
      global $hideScope;
      if ($attribute=='hidden' and !Project::isMultiCurrencyEnabled()) return true;
      if ($attribute=='hidden' and (!property_exists($this, 'idProject') or !$this->hasCurrency()) and $hideScope!='column' and $hideScope!='export') {
        return true;
      }
      if ($attribute=='hidden' and pq_strpos($this->getFieldAttributes($fieldName), 'visible')!==false) return false;
      if (!self::isPct($fieldName) and !self::isWork($fieldName) and !self::isDate($fieldName)) $fieldName=pq_substr($fieldName, 0, -5);
    } else {}
    if (pq_strpos($this->getFieldAttributes($fieldName), $attribute)!==false) {
      return true;
    } else {
      return false;
    }
  }

  public function getDisplayStyling($fieldName) {
    if (pq_substr($fieldName, -5)=='Local') $fieldName=pq_substr($fieldName, 0, -5);
    $displayStyling=$this->getStaticDisplayStyling();
    if (isset($displayStyling[$fieldName])) {
      $res=$displayStyling[$fieldName];
      if (!isset($res['caption'])) $res['caption']='';
      if (!isset($res['caption'])) $res['caption']='';
      return $res;
    } else {
      return array('caption'=>'', 'field'=>'');
    }
  }

  public function getStaticDisplayStyling() {
    return array();
  }

  /**
   * ========================================================================
   * Return the default value for a given field
   *
   * @return string the name of the data table
   */
  public function getDefaultValue($fieldName, $onSave=false) {
    $defaultValues=$this->getStaticDefaultValues();
    if (pq_array_key_exists($fieldName, $defaultValues)) {
      if (pq_substr($defaultValues[$fieldName], 0, pq_strlen(self::$_evaluationString))==self::$_evaluationString) {
        $value=""; // Not necessary, will be defined through evel(...), just keep it to avoid warning
        $eval=pq_substr($defaultValues[$fieldName], pq_strlen(self::$_evaluationString));
        // $eval='$value='. pq_str_replace("'",'"',$eval).";";
        $eval='$value=' . pq_str_replace('\$', '$', $eval) . ';';
        eval($eval);
        return $value;
      } else if ($onSave) {
        if ($this->getDataType($fieldName)=='int' and $this->getDataLength($fieldName)==1) {
          return ($defaultValues[$fieldName]=='on')?1:0;
        } else if ($this->getDataType($fieldName)=='varchar' and $this->getDataLength($fieldName)>4000) {
          return '<div>' . nl2br($defaultValues[$fieldName]) . '</div>';
        } else {
          return $defaultValues[$fieldName];
        }
      }
    } else {
      return null;
    }
  }

  public function getDefaultValueString($fieldName) {
    $defaultValues=$this->getStaticDefaultValues();
    if (pq_array_key_exists($fieldName, $defaultValues)) {
      return $defaultValues[$fieldName];
    } else {
      return null;
    }
  }

  public function checkValidEvaluationString($str) {
    if (pq_substr($str, 0, pq_strlen(self::$_evaluationString))!=self::$_evaluationString) return false;
    // Some check to avoid hack (even if this feature should only be given to admin)
    foreach (self::$_evaluationStringForbiddenKeywords as $keyword) {
      if (pq_strpos($str, $keyword)!==false) return false;
    }
    $eval=pq_substr($str, pq_strlen(self::$_evaluationString));
    $resultOkForCheckValidEvaluationString=false;
    $eval='$value=' . $eval . ';$resultOkForCheckValidEvaluationString=true;';
    disableCatchErrors();
    @eval($eval);
    enableCatchErrors();
    if (isset($resultOkForCheckValidEvaluationString) and $resultOkForCheckValidEvaluationString==true) return true;
    return false;
  }

  /**
   * ========================================================================
   * Return the default value for a given field
   *
   * @return string the name of the data table
   */
  public function setAllDefaultValues($onSave=false) {
    // Hint $onSave=2 means object is on creation, but already has id (for instance creation of Resource from User, check "is resource")
    $defaultValues=$this->getStaticDefaultValues();
    foreach ($defaultValues as $field=>$value) {
      if ($onSave) {
        if (($this->$field===null and (!$this->id or intval($onSave)==2)) or $this->isAttributeSetToField($field, 'readonly')) {
          $def=$this->getDefaultValue($field, (!$this->id or intval($onSave)==2)?true:false);
          if ($def!==null) $this->$field=$def;
        }
      } else {
        if (!$this->id) {
          $this->$field=$this->getDefaultValue($field, true);
        } else if ($this->$field===null and $this->isAttributeSetToField($field, 'required')) {
          $this->$field=$this->getDefaultValue($field);
        }
      }
    }
    // Set also criteria fields
    foreach ($this->getStaticDatabaseCriteria() as $crt=>$val) {
      if (property_exists($this, $crt)) {
        if ($crt!="isMaterial") {
          $this->$crt=$val;
        }
      }
    }
  }

  /**
   * ========================================================================
   * Return the name of the table in the database
   * Default is the name of the class (lowercase)
   * May be overloaded for some classes, who reference a table different
   * from class name
   *
   * @return string the name of the data table
   */
  public function getDatabaseTableName() {
    if (pq_substr(get_class($this), -4)=='Main') {
      $notMain=pq_substr(get_class($this), 0, -4);
      $obj=new $notMain();
      return $obj->getDatabaseTableName();
    } else {
      return $this->getStaticDatabaseTableName();
    }
  }

  /**
   * ========================================================================
   * Return the name of the column name in the table in the database
   * Default is the name of the field
   * May be overloaded for some fields of some classes
   *
   * @param string $field
   *          : The field to find as data column in database
   * @param boolean $emptyIfNotFound
   *          : If True = Returns empty string if not found
   * @return string the name of the data column
   */
  public function getDatabaseColumnName($field, $emptyIfNotFound=false) {
    $colName=$field;
    $databaseColumnName=$this->getStaticDatabaseColumnName();
    if (pq_array_key_exists($field, $databaseColumnName)) {
      $colName=$databaseColumnName[$field];
    } else if ($emptyIfNotFound) {
      return "";
    }
    // else {
    // return Sql::str($field); // Must not be quoted : would return 'name' (with quotes)
    // return $field;
    // }
    // if (Sql::isPgsql() ) {
    // $colName=pq_strtolower($colName);
    // }
    return $colName;
  }

  public function replaceDatabaseColumnNameInWhereClause($where) {
    foreach ($this->getStaticDatabaseColumnName() as $from=>$to) {
      $where=pq_str_replace($from, $to, $where);
    }
    return $where;
  }

  /**
   * ========================================================================
   * Return the name of the field in the object from the column name in the
   * table in the database
   * (it is the reversed method from getDatabaseColumnName()
   * Default is the name of the field
   * May be overloaded for some fields of some classes
   *
   * @return string the name of the data column
   */
  public function getDatabaseColumnNameReversed($field) {
    $databaseColumnName=$this->getStaticDatabaseColumnName();
    $databaseColumnNameReversed=array_flip(array_map('pq_strtolower', $databaseColumnName));
    $field=pq_strtolower($field);
    if (pq_array_key_exists(pq_strtolower($field), $databaseColumnNameReversed)) {
      return $databaseColumnNameReversed[$field];
    } else {
      return $field;
    }
  }

  /**
   * ========================================================================
   * Return the additional criteria to select class elements in the database
   * Default is empty string
   * May be overloaded for some classes, which reference a table different
   * from class name
   *
   * @return array listing criteria
   */
  public function getDatabaseCriteria() {
    return $this->getStaticDatabaseCriteria();
  }

  /**
   * ============================================================================
   * Return the caption of a field using i18n translation
   *
   * @param $fld String
   *          the name of the field
   * @return String the translated colXxxxxx value
   */
  function getColCaption($fld) {
    if (!$fld or $fld=='') {
      return '';
    }
    $extraCaption='';
    $colCaptionTransposition=$this->getStaticColCaptionTransposition($fld);
    if (pq_array_key_exists($fld, $colCaptionTransposition)) {
      $fldName=$colCaptionTransposition[$fld];
    } else {
      $fldName=$fld;
    }
    $caption=i18n('col' . pq_ucfirst($fldName)) . $extraCaption;
    if (pq_substr($caption, 0, 1)=='[' and pq_substr($fldName, -5)=='Local') {
      $fldName=pq_substr($fldName, 0, -5);
      $caption=i18n('col' . pq_ucfirst($fldName));
      global $hideScope;
      if ($hideScope=='column' or $hideScope=='export') $caption.=' (' . i18n('colLocal') . ')';
    }
    return $caption;
  }

  /**
   * ============================================================================
   * Return the transposition of a field
   *
   * @param $fld String
   *          the name of the field
   * @return String the transposition value
   */
  function getColTransposition($fld) {
    if (!$fld or $fld=='') {
      return '';
    }
    $colCaptionTransposition=$this->getStaticColCaptionTransposition($fld);
    if (pq_array_key_exists($fld, $colCaptionTransposition)) {
      $fldName=$colCaptionTransposition[$fld];
    } else {
      $fldName=$fld;
    }
    return $fldName;
  }

  public function getLowercaseFieldsArray($limitToExportableFields=false) {
    $arrayFields=array();
    if (method_exists($this, 'setAttributes')) $this->setAttributes();
    $extraHiddenFields=$this->getExtraHiddenFields((($limitToExportableFields)?'*':null), null, getSessionUser()->getProfile(), $limitToExportableFields);
    foreach ($this as $fld=>$fldVal) {
      if (is_object($this->$fld)) {
        $arrayFields=array_merge($arrayFields, $this->$fld->getLowercaseFieldsArray($limitToExportableFields));
      } else {
        if ($limitToExportableFields and $fld!='id') {
          $fldTest=$fld;
          if ($fld=='inheritedEndDate' and Parameter::getGlobalParameter('gestionInheritedEndDate')!='NO') $fldTest='validatedEndDate';
          if (($this->isAttributeSetToField($fldTest, 'hidden') or $this->isAttributeSetToField($fldTest, 'hiddenforce') or in_array($fldTest, $extraHiddenFields)) and !$this->isAttributeSetToField($fldTest, 'forceExport')) continue;
        }
        $arrayFields[pq_strtolower($fld)]=$fld;
      }
    }
    return $arrayFields;
  }

  // public function getFieldsList() {
  // $list=array();
  // $reflector = new ReflectionClass($this);
  // $props=$reflector->getProperties(ReflectionProperty::IS_PUBLIC); // ReflectionProperty::IS_PUBLIC | ReflectionProperty::IS_PROTECTED
  // foreach($props as $prop) {
  // $list[]=$prop->getName();
  // }
  // return $list;
  // }
  function getFieldsList($types='public') {
    if (isset(self::$_fieldsLists[get_class($this)])) return self::$_fieldsLists[get_class($this)];
    $ref=new ReflectionClass($this);
    $props=$ref->getProperties();
    $result=array();
    foreach ($props as $prop) {
      if ($prop->isPublic() and (pq_stripos($types, 'public')===FALSE)) continue;
      if ($prop->isPrivate() and (pq_stripos($types, 'private')===FALSE)) continue;
      if ($prop->isProtected() and (pq_stripos($types, 'protected')===FALSE)) continue;
      if ($prop->isStatic() and (pq_stripos($types, 'static')===FALSE)) continue;
      if (!pq_array_key_exists($prop->getName(), (array)$this)) continue; // property has been unset
      $result[]=$prop->getName();
    }
    $parentClass=$ref->getParentClass();
    if ($parentClass and !$parentClass->isAbstract()) {
      $parentClassName=$parentClass->getName();
      $parent=new $parentClassName();
      $parentProps=$parent->getFieldsList($types);
      foreach ($parentProps as $prop) {
        if (!in_array($prop, $result)) {
          $result[]=$prop;
        }
      }
    }
    self::$_fieldsLists[get_class($this)]=$result;
    return $result;
  }

  public function getFieldsArray($limitToExportableFields=false) {
    // Old style to list fields is enough as order for items is not specifically required
    $arrayFields=array();
    if (method_exists($this, 'setAttributes')) $this->setAttributes();
    $extraHiddenFields=$this->getExtraHiddenFields((($limitToExportableFields)?'*':null), null, getSessionUser()->getProfile(), $limitToExportableFields);
    foreach ($this as $fld=>$fldVal) {
      if (is_object($this->$fld)) {
        $arrayFields=array_merge($arrayFields, $this->$fld->getFieldsArray($limitToExportableFields));
      } else {
        if ($limitToExportableFields and $fld!='id') {
          // CHANGE BY Marc TABARY - 2017-03-20 - FORCE HIDDEN OR READONLY
          $fldTest=$fld;
          if ($fld=='inheritedEndDate' and Parameter::getGlobalParameter('gestionInheritedEndDate')!='NO') $fldTest='validatedEndDate';
          if (($this->isAttributeSetToField($fldTest, 'hidden') or $this->isAttributeSetToField($fldTest, 'hiddenforce') or in_array($fldTest, $extraHiddenFields)) and !$this->isAttributeSetToField($fldTest, 'forceExport')) {
            continue;
          }
        }
        $arrayFields[$fld]=$fld;
      }
    }
    return $arrayFields;
  }

  public function listNumericFieldsForSum($included=false) {
    // return result in json format
    $result=array();
    if (method_exists($this, 'setAttributes')) $this->setAttributes();
    foreach ($this as $col=>$val) {
      if (is_object($val)) {
        $result=array_merge_preserve_keys($result, $val->listNumericFieldsForSum(true));
      }
      if (pq_substr($col, 0, 1)=="_") continue; // Technical field
      if ($this->isAttributeSetToField($col, 'hidden')) continue; // Do not show hidden fileds
      if ($this->isAttributeSetToField($col, 'notSummable')) continue; // New attribute to hide is wanted
      if ($included and ($col=='id' or $col=='refType' or $col=='refId' or $col=='idle')) continue;
      $dataType=$this->getDataType($col);
      $dataLength=$this->getDataLength($col);
      if ($dataType=='int' and $dataLength==1) continue; // Boolean
      if ($dataType=='int' and $dataLength==12) continue; // Id
      if ($dataType=='int' and $col=='sortOrder' or $col=='order') continue; // sort fields
      if (isForeignKey($col)) continue; // Foreign key $idXxxxx or $idYyyyy_idXxxxx
      if ($dataType=='numeric' or $dataType=='decimal' or $dataType=='int') {
        $colName=$this->getColCaption($col);
        $result[$col]=$colName;
      }
    }
    return $result;
  }

  /**
   * =========================================================================
   * Return the list of fields format and store it in static array of formats
   * to be able to fetch it again without requesting it from database
   *
   * @param $class String
   *          the class of the object
   * @return String the format list
   */
  private static function getFormatList($class) {
    if (count(self::$_tablesFormatList)==0) { // if static value not initalized, try and retrieve from session
      $fromSession=getSessionValue('_tablesFormatList');
      if ($fromSession==null) {
        setSessionValue('_tablesFormatList', self::$_tablesFormatList);
      } else {
        self::$_tablesFormatList=$fromSession;
      }
    }
    if (pq_array_key_exists($class, self::$_tablesFormatList)) {
      return self::$_tablesFormatList[$class];
    }
    $obj=new $class();
    $formatList=array();
    $query="desc " . $obj->getDatabaseTableName();
    if (Sql::isPgsql()) {
      $query="SELECT a.attname as field, pg_catalog.format_type(a.atttypid, a.atttypmod) as type" . " FROM pg_catalog.pg_attribute a " . " WHERE a.attrelid = (SELECT oid FROM pg_catalog.pg_class WHERE relname='" . $obj->getDatabaseTableName() . "')" . " AND a.attnum > 0 AND NOT a.attisdropped" . " ORDER BY a.attnum";
    }
    $result=Sql::query($query);
    while ($line=Sql::fetchLine($result)) {
      if (!isset($line['Field']) and !isset($line['field'])) {
        debugTraceLog("SqlElement::getFormatList($class) : result has no column 'field'");
        debugTraceLog($line);
        continue;
      }
      $dbFieldName=(isset($line['Field']))?$line['Field']:$line['field'];
      $fieldName=$obj->getDatabaseColumnNameReversed($dbFieldName);
      $type=(isset($line['Type']))?$line['Type']:$line['type'];
      $from=array();
      $to=array();
      if (Sql::isPgsql()) {
        $from[]='integer';
        $to[]='int(12)';
        $from[]='numeric(12,0)';
        $to[]='int(12)';
        $from[]='numeric(5,0)';
        $to[]='int(5)';
        $from[]='numeric(3,0)';
        $to[]='int(3)';
        $from[]='numeric(1,0)';
        $to[]='int(1)';
        $from[]=' without time zone';
        $to[]='';
        $from[]='character varying';
        $to[]='varchar';
        $from[]='numeric';
        $to[]='decimal';
        $from[]='timestamp';
        $to[]='datetime';
      }
      $from[]='mediumtext';
      $to[]='varchar(16777215)';
      $from[]='longtext';
      $to[]='varchar(4294967295)';
      $from[]='text';
      $to[]='varchar(65535)';
      $from[]='bigint';
      $to[]='int';
      $from[]='int unsigned';
      $to[]='int';

      $type=str_ireplace($from, $to, $type);
      if (pq_substr($type, 0, 3)=='int') $type=pq_trim(pq_str_replace('unsigned', '', $type));
      if ($fieldName=='id') {
        $type='int(12)';
      } else if (($type=='int' or $type=='int(10)' or $type=='int(11)') and !Sql::isPgsql()) {
        $tableName=$obj->getDatabaseTableName();
        // $dbName=Parameter::getGlobalParameter('paramDbName');
        // $sqlColumn="SELECT COLUMN_COMMENT as comment FROM INFORMATION_SCHEMA.COLUMNS "
        // ." WHERE TABLE_SCHEMA='$dbName' AND TABLE_NAME='$tableName' AND COLUMN_NAME='$dbFieldName'";
        // $resultColumn=Sql::query($sqlColumn);
        // $line=Sql::fetchLine($resultColumn);
        // if ($line and isset($line['comment'])) $type='int('.$line['comment'].')';
        if (!isset(self::$_tablesFormatListColumns[$tableName])) {
          self::$_tablesFormatListColumns[$tableName]=array();
          $dbName=Parameter::getGlobalParameter('paramDbName');
          $sqlColumn="SELECT COLUMN_NAME as colname, COLUMN_COMMENT as comment FROM INFORMATION_SCHEMA.COLUMNS " . " WHERE TABLE_SCHEMA='$dbName' AND TABLE_NAME='$tableName'";
          $resultColumn=Sql::query($sqlColumn);
          while ($line=Sql::fetchLine($resultColumn)) {
            self::$_tablesFormatListColumns[$tableName][$line['colname']]=$line['comment'];
          }
        }
        $type='int(' . self::$_tablesFormatListColumns[$tableName][$dbFieldName] . ')';
      }
      $formatList[pq_strtolower($fieldName)]=$type;
      if (pq_strtolower($fieldName)=='idplanningmode') {
        $pmFld='id' . pq_str_replace('PlanningElement', '', $class) . 'PlanningMode';
        $formatList[pq_strtolower($pmFld)]=$type;
      } else if ($fieldName=='id' . pq_str_replace('PlanningElement', '', $class) . 'PlanningMode') {
        $formatList['idplanningmode']=$type;
      }
    }
    self::$_tablesFormatList[$class]=$formatList;
    setSessionValue('_tablesFormatList', self::$_tablesFormatList); // store session value (as initalized)
    return $formatList;
  }

  /**
   * ========================================================================
   * return the generic layout
   *
   * @return String the layout from static data
   */
  protected function getStaticLayout() {
    return self::$_layout;
  }

  // ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
  /**
   * ==========================================================================
   * Return the generic disabledFieldOnChange
   *
   * @return Array array[name] : the generic $_disabledFieldOnChange
   */
  protected function getStaticDisabledFieldsOnChange() {
    return self::$_disabledFieldsOnChange;
  }

  // END ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET

  // ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER
  /**
   * ==========================================================================
   * Return the generic spinnerAttributes
   *
   * @return Array array[name,value] : the generic $_spinnerAttributes
   */
  protected function getStaticSpinnersAttributes() {
    return self::$_spinnersAttributes;
  }

  // END ADD BY Marc TABARY - 2017-03-02 - DRAW SPINNER

  // BEGIN - ADD BY TABARY - TOOLTIP
  /**
   * ==========================================================================
   * Return the generic fieldsTooltip
   *
   * @return array the fieldsTooltip array
   */
  protected function getStaticFieldsTooltip() {
    return self::$_fieldsTooltip;
  }

  // END - ADD BY TABARY - TOOLTIP

  /**
   * ==========================================================================
   * Return the generic fieldsAttributes
   *
   * @return String the layout
   */
  protected function getStaticFieldsAttributes() {
    return self::$_fieldsAttributes;
  }

  /**
   * ==========================================================================
   * Return the generic defaultValues
   *
   * @return String the layout
   */
  protected function getStaticDefaultValues() {
    return self::$_defaultValues;
  }

  /**
   * ==========================================================================
   * Return the generic databaseTableName
   *
   * @return String the layout
   */
  protected function getStaticDatabaseTableName() {
    $paramDbPrefix=Parameter::getGlobalParameter('paramDbPrefix');
    return pq_strtolower($paramDbPrefix . get_class($this));
  }

  /**
   * ========================================================================
   * Return the generic databaseTableName
   *
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseColumnName() {
    return array();
  }

  /**
   * ========================================================================
   * Return the generic database criteria
   *
   * @return String the databaseTableName
   */
  protected function getStaticDatabaseCriteria() {
    return array();
  }

  /**
   * ============================================================================
   * Return the specific colCaptionTransposition
   *
   * @return String the colCaptionTransposition
   */
  protected function getStaticColCaptionTransposition($fld=null) {
    return array();
  }

  // ============================================================================**********
  // GET VALIDATION SCRIPT
  // ============================================================================**********

  /**
   * ========================================================================
   * return generic javascript to be executed on validation of field
   *
   * @param $colName String
   *          the name of the column
   * @return String the javascript code
   */
  public function getValidationScript($colName) {
    $colScript='';
    $posDate=pq_strlen($colName)-4;

    // ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
    $specificWidgetsToDisabled=$this->getDisabledFieldsOnChange();
    // END ADD BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET

    if (pq_substr($colName, 0, 2)=='id' and pq_strlen($colName)>2) { // SELECT => onChange
      $colScript.='<script type="dojo/connect" event="onChange" args="evt">';
      $colScript.='  if (this.value!=null && this.value!="") { ';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='  }';
      // if ( get_class($this)=='Activity' or get_class($this)=='Ticket' or get_class($this)=='Milestone' ) {
      if (get_class($this)!='Project' and get_class($this)!='Affectation') {
        if ($colName=='idProject' and property_exists($this, 'idActivity')) {
          $colScript.='   refreshList("idActivity","idProject", this.value);';
        }
        if ($colName=='idProject' and property_exists($this, 'idResource')) {
          $required='false';
          if ($this->isAttributeSetToField('idResource', 'required')) $required='true';
          $colScript.='   refreshList("idResource","idProject", this.value, "' . htmlEncode($this->idResource) . '",null,' . $required . ',null,null,"' . get_class($this) . '");';
          foreach ($this as $tmpCol=>$tmpVal) {
            if (pq_substr($tmpCol, -12)=='__idResource') {
              $tmpReq='false';
              if ($this->isAttributeSetToField($tmpCol, 'required')) $tmpReq='true';
              $colScript.='   refreshList("' . $tmpCol . '","idProject", this.value, "' . htmlEncode($tmpVal) . '",null,' . $tmpReq . ',null,null,"' . get_class($this) . '");';
            }
          }
        }
        if ($colName=='idProject' and property_exists($this, 'idAccountable')) {
          $required='false';
          if ($this->isAttributeSetToField('idAccountable', 'required')) $required='true';
          $colScript.='   refreshList("idAccountable","idProject", this.value, "' . htmlEncode($this->idAccountable) . '",null,' . $required . ',null,null,"' . get_class($this) . '");';
        }
        if ($colName=='idProject' and property_exists($this, 'idAffectable')) {
          $required='false';
          if ($this->isAttributeSetToField('idAffectable', 'required')) $required='true';
          $colScript.='   refreshList("idAffectable","idProject", this.value, "' . htmlEncode($this->idAffectable) . '",null,' . $required . ',null,null,"' . get_class($this) . '");';
        }
        if ($colName=='idProject' and property_exists($this, 'idProduct')) {
          $colScript.='   refreshList("idProduct","idProject", this.value, dijit.byId("idProduct").get("value"));';
        }
        if ($colName=='idProject' and property_exists($this, 'idComponent')) {
          $colScript.='   if (dijit.byId("idProduct") && trim(dijit.byId("idProduct").get("value"))) {';
          // $colScript .= ' refreshList("idComponent","idProduct", dijit.byId("idProduct").get("value"), dijit.byId("idComponent").get("value"));';
          $colScript.='   } else {';
          $colScript.='     refreshList("idComponent","idProject", this.value, dijit.byId("idComponent").get("value"));';
          $colScript.='   }';
        }
        if ($colName=='idProject' and property_exists($this, 'idProductOrComponent')) {
          $colScript.='   refreshList("idProductOrComponent","idProject", this.value, dijit.byId("idProductOrComponent").get("value"));';
        }
        if ($colName=='idProject' and property_exists($this, SqlElement::getTypeName(get_class($this)))) {
          $colScript.='   refreshList("' . SqlElement::getTypeName(get_class($this)) . '","idProject", this.value, dijit.byId("' . SqlElement::getTypeName(get_class($this)) . '").get("value"),null,true);';
        }
        if ($colName=='idProject' and property_exists($this, 'idMilestone')) {
          $colScript.='   refreshList("idMilestone","idProject", this.value);';
        }
        if ($colName=='idProject' and property_exists($this, 'idDocumentDirectory')) {
          $colScript.='   refreshList("idDocumentDirectory","idProject", this.value);';
        }
        if ($colName=='idProject' and Parameter::getGlobalParameter('allowListRestrictionOnProject')=='YES') {
          $rList=ListHideValue::getRestrictedLists();
          foreach ($rList as $valList) {
            if (property_exists($this, 'id' . $valList)) {
              $colScript.='   if (dijit.byId("id' . $valList . '")) refreshList("id' . $valList . '","idProject", this.value);';
            }
          }
        }
        if ($colName=="idProject" and property_exists($this, 'tags') and Parameter::getGlobalParameter('listTagsPerProject')=='YES') {
          $colScript.='  refreshListSpecific("listTagPerProject", "tagInput", "idProject", this.value, null, null, "refType", "' . get_class($this) . '");';
        }
        $arrVers=array(
            'idVersion',
            'idProductVersion',
            'idOriginalVersion',
            'idOriginalProductVersion',
            'idOriginalComponentVersion',
            'idTargetVersion',
            'idTargetProductVersion',
            'idTargetComponentVersion',
            'idTestCase',
            'idRequirement');
        $arrVersProd=array(
            'idVersion',
            'idProductVersion',
            'idOriginalVersion',
            'idOriginalProductVersion',
            'idTargetVersion',
            'idTargetProductVersion',
            'idTestCase',
            'idRequirement');
        $arrVersComp=array('idVersion', 'idComponentVersion', 'idOriginalComponentVersion', 'idTargetComponentVersion');
        $versionExists=false;
        foreach ($arrVers as $vers) {
          if (property_exists($this, $vers)) {
            $versionExists=true;
          }
        }
        if ($colName=='idProject' and $versionExists) {
          foreach ($arrVersComp as $vers) {
            if (property_exists($this, $vers)) {
              $versProd=pq_str_replace('Component', 'Product', $vers);
              $colScript.="if (dijit.byId('$versProd') && trim(dijit.byId('$versProd').get('value')) ) {";
              // $colScript.="refreshList('$vers','$versProd', dijit.byId('$versProd').get('value'));";
              $colScript.=" } else if (dijit.byId('idComponent') && trim(dijit.byId('idComponent').get('value'))) {";
              // $colScript.="refreshList('$vers','idComponent', trim(dijit.byId('idComponent').get('value')));";
              $colScript.=" } else {";
              $colScript.="refreshList('$vers','idProject', this.value);";
              $colScript.=" }";
            }
          }
          foreach ($arrVersProd as $vers) {
            if (property_exists($this, $vers)) {
              $colScript.=" if (dijit.byId('idProduct') && trim(dijit.byId('idProduct').get('value'))) {";
              // $colScript.="refreshList('$vers','idProduct', trim(dijit.byId('idProduct').get('value')));";
              $colScript.=" } else {";
              $colScript.="refreshList('$vers','idProject', this.value);";
              $colScript.=" }";
            }
          }
        }
        if ($colName=='idProduct' and property_exists($this, 'idComponent')) {
          $colScript.="if (trim(this.value)) {";
          $colScript.="refreshList('idComponent','idProduct', this.value);";
          $colScript.="} else {";
          if (property_exists($this, 'idProject')) {
            $colScript.="refreshList('idComponent','idProject', dijit.byId('idProject').get('value'));";
          }
          $colScript.="}";
        }
        if ($colName=='idProduct' and $versionExists) {
          foreach ($arrVersProd as $vers) {
            if (property_exists($this, $vers)) {
              $colScript.="if (trim(dijit.byId('idProduct').get('value'))) {";
              if (property_exists($this, 'idProject')) {
                $colScript.="refreshList('$vers','idProduct', this.value, null, null, null, 'idProject', dijit.byId('idProject').get('value'));";
              } else {
                $colScript.="refreshList('$vers','idProduct', this.value);";
              }
              $colScript.="} else {";
              if (property_exists($this, 'idProject')) {
                $colScript.="refreshList('$vers','idProject', dijit.byId('idProject').get('value'));";
              }
              $colScript.="}";
            }
          }
        }
        if ($colName=='idProduct' and property_exists($this, 'idBusinessFeature')) {
          $colScript.="refreshList('idBusinessFeature','idProduct', this.value);";
        }
        if ($colName=='idComponent' and $versionExists) {
          foreach ($arrVersComp as $vers) {
            if (property_exists($this, $vers)) {
              $versProd=pq_str_replace('Component', 'Product', $vers);
              $colScript.="if (dijit.byId('$versProd') && trim(dijit.byId('$versProd').get('value'))) {";
              $colScript.="  if (trim(this.value)) {";
              $colScript.="  refreshList('$vers','idProductVersion', dijit.byId('$versProd').get('value'), null, null,null,'idComponent',this.value);";
              $colScript.="  } else {";
              $colScript.="  refreshList('$vers','idProductVersion', dijit.byId('$versProd').get('value'));";
              $colScript.="  }";
              $colScript.="} else if (trim(this.value)) {";
              $colScript.="refreshList('$vers','idComponent', this.value);";
              $colScript.="} else {";
              if (property_exists($this, 'idProject')) {
                $colScript.="refreshList('$vers','idProject', dijit.byId('idProject').get('value'));";
              }
              $colScript.="}";
            }
          }
        }
        if (pq_substr($colName, -14)=='ProductVersion') {
          $versComp=pq_str_replace('Product', 'Component', $colName);
          if (property_exists($this, $versComp)) {
            $colScript.="if (trim(this.value)) {";
            if (property_exists($this, 'idComponent')) {
              $colScript.="  if (dijit.byId('idComponent') && trim(dijit.byId('idComponent').get('value')) ) {";
              $colScript.="refreshList('$versComp','idProductVersion', this.value, null, null, null,'idComponent', dijit.byId('idComponent').get('value'));";
              $colScript.=" } else {";
              $colScript.="refreshList('$versComp','idProductVersion', this.value);";
              $colScript.=" }";
            }
            if (property_exists($this, 'idComponent')) {
              $colScript.="} else if (dijit.byId('idComponent') && trim(dijit.byId('idComponent').get('value')) ) {";
              $colScript.="refreshList('$versComp','idComponent', dijit.byId('idComponent').get('value'));";
            }
            $colScript.="} else {";
            if (property_exists($this, 'idProject')) {
              $colScript.="refreshList('$versComp','idProject', dijit.byId('idProject').get('value'));";
            }
            $colScript.="}";
          }
          if (property_exists($this, 'idProduct')) {
            $colScript.='if (! trim(dijit.byId("idProduct").get("value")) ) {';
            $colScript.='   setProductValueFromVersion("idProduct",this.value);';
            $colScript.='}';
          }
        }
        if (pq_substr($colName, -16)=='ComponentVersion') {
          if (property_exists($this, 'idProduct')) {
            $colScript.='if (! trim(dijit.byId("idComponent").get("value")) ) {';
            $colScript.='   setProductValueFromVersion("idComponent",this.value);';
            $colScript.='}';
          }
        }
        if ($colName=='idProject' and property_exists($this, 'idContact')) {
          $colScript.='   refreshList("idContact","idProject", this.value);';
        }
        if ($colName=='idProject' and property_exists($this, 'idAffectable')) {
          $colScript.='   refreshList("idAffectable","idProject", this.value);';
        }
        if ($colName=='idProject' and property_exists($this, 'idTicket')) {
          $colScript.='   refreshList("idTicket","idProject", this.value);';
        }
        if ($colName=='idProject' and property_exists($this, 'idUser')) {
          $colScript.='   refreshList("idUser","idProject", this.value);';
        }
      }
      // $typeName='id' . get_class ( $this ) . 'Type';
      // if (get_class($this)=='PeriodicMeeting') $typeName='idMeetingType';
      $typeName=self::getTypeName(get_class($this));
      if ($colName=='idStatus' or $colName==$typeName or pq_substr($colName, -12)=='PlanningMode' or $colName=='isResource' or $colName=='isUser') {
        $colScript.='   getExtraRequiredFields();';
      }
      if ($colName==$typeName or $colName=='idStatus') {
        $colScript.='   getExtraReadonlyFields("","","");';
        // MTY - LEAVE SYSTEM
        if (get_class($this)!="Leave") {
          $colScript.='   getExtraHiddenFields("","","");';
        }
        // MTY - LEAVE SYSTEM
      }
      $colScript.='</script>';
    }
    if (pq_substr($colName, $posDate, 4)=='Date') { // Date => onChange
      $colScript.='<script type="dojo/connect" event="onChange">';
      $colScript.='  if (this.value!=null && this.value!="") { ';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='  }';
      $colScript.='</script>';
    }
    if (!(pq_substr($colName, 0, 2)=='id' and pq_strlen($colName)>2)) { // OTHER => onKeyPress
      $colScript.='<script type="dojo/method" event="onKeyDown" args="event">'; // V4.2 Changed onKeyPress to onKeyDown because was not triggered
      $colScript.='  if (isEditingKey(event)) {';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='  }';
      $colScript.='</script>';
    }
    if ($colName=="idStatus") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      if (property_exists($this, 'idle') and get_class($this)!='StatusMail') {
        $colScript.=htmlGetJsTable('Status', 'setIdleStatus', 'tabStatusIdle');
        $colScript.='  var setIdle=0;';
        $colScript.='  var filterStatusIdle=dojo.filter(tabStatusIdle, function(item){return item.id==dijit.byId("idStatus").value;});';
        $colScript.='  dojo.forEach(filterStatusIdle, function(item, i) {setIdle=item.setIdleStatus;});';
        $colScript.='  if (setIdle==1) {';
        $colScript.='    dijit.byId("idle").set("checked", true);';
        $colScript.='  } else {';
        $colScript.='    dijit.byId("idle").set("checked", false);';
        $colScript.='  }';
      }
      if (property_exists($this, 'done')) {
        $colScript.=htmlGetJsTable('Status', 'setDoneStatus', 'tabStatusDone');
        $colScript.='  var setDone=0;';
        $colScript.='  var filterStatusDone=dojo.filter(tabStatusDone, function(item){return item.id==dijit.byId("idStatus").value;});';
        $colScript.='  dojo.forEach(filterStatusDone, function(item, i) {setDone=item.setDoneStatus;});';
        $colScript.='  if (setDone==1) {';
        $colScript.='    dijit.byId("done").set("checked", true);';
        $colScript.='  } else {';
        $colScript.='    dijit.byId("done").set("checked", false);';
        $colScript.='  }';
      }
      if (property_exists($this, 'handled')) {
        $colScript.=htmlGetJsTable('Status', 'setHandledStatus', 'tabStatusHandled');
        $colScript.='  var setHandled=0;';
        $colScript.='  var filterStatusHandled=dojo.filter(tabStatusHandled, function(item){return item.id==dijit.byId("idStatus").value;});';
        $colScript.='  dojo.forEach(filterStatusHandled, function(item, i) {setHandled=item.setHandledStatus;});';
        $colScript.='  if (setHandled==1) {';
        $colScript.='    dijit.byId("handled").set("checked", true);';
        $colScript.='  } else {';
        $colScript.='    dijit.byId("handled").set("checked", false);';
        $colScript.='  }';
      }
      if (property_exists($this, 'cancelled')) {
        $colScript.=htmlGetJsTable('Status', 'setCancelledStatus', 'tabStatusCancelled');
        $colScript.='  var setCancelled=0;';
        $colScript.='  var filterStatusCancelled=dojo.filter(tabStatusCancelled, function(item){return item.id==dijit.byId("idStatus").value;});';
        $colScript.='  dojo.forEach(filterStatusCancelled, function(item, i) {setCancelled=item.setCancelledStatus;});';
        $colScript.='  if (setCancelled==1) {';
        $colScript.='    dijit.byId("cancelled").set("checked", true);';
        $colScript.='  } else {';
        $colScript.='    dijit.byId("cancelled").set("checked", false);';
        $colScript.='  }';
      }
      if (property_exists($this, 'paused')) {
        $colScript.=htmlGetJsTable('Status', 'setPausedStatus', 'tabStatusPaused');
        $previousSetPausedStatus=(SqlList::getFieldFromId("Status", $this->idStatus, "setPausedStatus")!=0)?1:0;
        $colScript.='  var setPaused=0;';
        $colScript.='  var statusWidget=dijit.byId("idStatus");';
        $colScript.='  var previousSetPausedStatus=(typeof statusWidget.previousSetPausedStatus=="undefined")?'.$previousSetPausedStatus.':statusWidget.previousSetPausedStatus;';
        $colScript.='  var filterStatusPaused=dojo.filter(tabStatusPaused, function(item){return item.id==dijit.byId("idStatus").value;});';
        $colScript.='  dojo.forEach(filterStatusPaused, function(item, i) {setPaused=item.setPausedStatus;});';
        $colScript.='  if (setPaused==1 && previousSetPausedStatus!=1) {';
        $colScript.='    dijit.byId("paused").set("checked", true);';
        $colScript.='  } else if (setPaused!=1 && previousSetPausedStatus==1) {';
        $colScript.='    dijit.byId("paused").set("checked", false);';
        $colScript.='  }';
        $colScript.='  statusWidget.previousSetPausedStatus=setPaused;';
      }
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='</script>';
    } else if ($colName=="idResolution") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      if (property_exists($this, 'solved')) {
        $colScript.=htmlGetJsTable('Resolution', 'solved', 'tabResolutionSolved');
        $colScript.='  var solved=0;';
        $colScript.='  var filterResolutionSolved=dojo.filter(tabResolutionSolved, function(item){return item.id==dijit.byId("idResolution").value;});';
        $colScript.='  dojo.forEach(filterResolutionSolved, function(item, i) {solved=item.solved;});';
        $colScript.='  if (solved==1) {';
        $colScript.='    dijit.byId("solved").set("checked", true);';
        $colScript.='  } else {';
        $colScript.='    dijit.byId("solved").set("checked", false);';
        $colScript.='  }';
      }
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='</script>';
    } else if ($colName=="idle") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      $colScript.='  if (this.checked) { ';
      if (property_exists($this, 'idleDateTime')) {
        $colScript.='    if (! dijit.byId("idleDateTime").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("idleDateTime").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='      dijit.byId("idleDateTimeBis").set("value", curDate.toISOString()); ';
        $colScript.='    }';
      }
      if (property_exists($this, 'idleDate')) {
        $colScript.='    if (! dijit.byId("idleDate").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("idleDate").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='    }';
      }
      // ADD tLaguerie ticket #396
      if (property_exists($this, 'endDate') and get_class($this)!='SupplierContract' and get_class($this)!='ClientContract') {
        $colScript.='    if(! dijit.byId("endDate").get("value")) {';
        $colScript.='       var curDate = new Date();';
        $colScript.='       dijit.byId("endDate").set("value", curDate.toISOString().slice(0,10));';
        $colScript.='    } ';
      }
      // END tLaguerie ticket #396
      /*
       * if (property_exists($this, 'done')) { // Removed : this is now driven by status
       * $colScript .= ' if (! dijit.byId("done").get("checked")) {';
       * $colScript .= ' dijit.byId("done").set("checked", true);';
       * $colScript .= ' }';
       * }
       */
      /*
       * if (property_exists($this, 'handled')) { // Removed : this is now driven by status
       * $colScript .= ' if (! dijit.byId("handled").get("checked")) {';
       * $colScript .= ' dijit.byId("handled").set("checked", true);';
       * $colScript .= ' }';
       * }
       */
      $colScript.='  } else {';
      // ADD tLaguerie ticket #396
      if (property_exists($this, 'endDate') and get_class($this)!='SupplierContract' and get_class($this)!='ClientContract') {
        $colScript.='    dijit.byId("endDate").set("value", null); ';
        $colScript.='    if (dijit.byId("endDateBis")) dijit.byId("endDateBis").set("value", null); ';
      }
      // END tLaguerie ticket #396
      if (property_exists($this, 'idleDateTime')) {
        $colScript.='    dijit.byId("idleDateTime").set("value", null); ';
        $colScript.='    dijit.byId("idleDateTimeBis").set("value", null); ';
      }
      if (property_exists($this, 'idleDate')) {
        $colScript.='    dijit.byId("idleDate").set("value", null); ';
      }
      $colScript.='  } ';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='</script>';
      // ADD tLaguerie ticket #396
    } else if ($colName=="isResource") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      $colScript.='  if (this.checked) { ';

      if (property_exists($this, 'startDate')) {
        $colScript.='    if(! dijit.byId("startDate").get("value")) {';
        $colScript.='       var curDate = new Date();';
        $colScript.='       dijit.byId("startDate").set("value", curDate.toISOString().slice(0,10));';
        $colScript.='    } ';
      }
      $colScript.='} else {';
      if (property_exists($this, 'startDate')) {
        $colScript.='    dijit.byId("startDate").set("value", null); ';
      }
      $colScript.='    } ';
      $colScript.='</script>';
      // END tLaguerie ticket #396
    } else if ($colName=="done") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      $colScript.='  if (this.checked) { ';
      if (property_exists($this, 'doneDateTime')) {
        $colScript.='    if (! dijit.byId("doneDateTime").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("doneDateTime").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='      dijit.byId("doneDateTimeBis").set("value", curDate.toISOString()); ';
        $colScript.='    }';
      }
      if (property_exists($this, 'doneDate')) {
        $colScript.='    if (! dijit.byId("doneDate").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("doneDate").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='    }';
      }
      if (property_exists($this, 'handled')) {
        $colScript.='    if (! dijit.byId("handled").get("checked")) {';
        $colScript.='      dijit.byId("handled").set("checked", true);';
        $colScript.='    }';
      }
      $colScript.='  } else {';
      if (property_exists($this, 'doneDateTime')) {
        $colScript.='    dijit.byId("doneDateTime").set("value", null); ';
        $colScript.='    dijit.byId("doneDateTimeBis").set("value", null); ';
      }
      if (property_exists($this, 'doneDate')) {
        $colScript.='    dijit.byId("doneDate").set("value", null); ';
      }
      if (property_exists($this, 'idle')) {
        $colScript.='    cancelled=(dijit.byId("cancelled") && dijit.byId("cancelled").get("checked"))?true:false;';
        $colScript.='    if (dijit.byId("idle").get("checked") && !cancelled) {';
        $colScript.='      dijit.byId("idle").set("checked", false);';
        $colScript.='    }';
      }
      $colScript.='  } ';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='</script>';
    } else if ($colName=="handled") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      $colScript.='  if (this.checked) { ';
      if (property_exists($this, 'handledDateTime')) {
        $colScript.='    if ( ! dijit.byId("handledDateTime").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("handledDateTime").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='      dijit.byId("handledDateTimeBis").set("value", curDate.toISOString()); ';
        $colScript.='    }';
      }
      if (property_exists($this, 'handledDate')) {
        $colScript.='    if (! dijit.byId("handledDate").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("handledDate").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='    }';
      }
      if (property_exists($this, 'isUnderConstruction')) {
        $colScript.='      if (dijit.byId("isUnderConstruction")) dijit.byId("isUnderConstruction").set("checked", false);';
      }
      $colScript.='  } else {';
      if (property_exists($this, 'handledDateTime')) {
        $colScript.='    dijit.byId("handledDateTime").set("value", null); ';
        $colScript.='    dijit.byId("handledDateTimeBis").set("value", null); ';
      }
      if (property_exists($this, 'handledDate')) {
        $colScript.='    dijit.byId("handledDate").set("value", null); ';
      }
      if (property_exists($this, 'done')) {
        $colScript.='    if (dijit.byId("done").get("checked")) {';
        $colScript.='      dijit.byId("done").set("checked", false);';
        $colScript.='    }';
      }
      if (property_exists($this, 'idle')) {
        $colScript.='    cancelled=(dijit.byId("cancelled") && dijit.byId("cancelled").get("checked"))?true:false;';
        $colScript.='    if (dijit.byId("idle").get("checked") && !cancelled) {';
        $colScript.='      dijit.byId("idle").set("checked", false);';
        $colScript.='    }';
      }
      $colScript.='  } ';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='</script>';
    } else if ($colName=="paused") {
      $colScript.='<script type="dojo/connect" event="onChange" >';
      $colScript.='  if (this.checked) { ';
      if (property_exists($this, 'pausedDateTime')) {
        $colScript.='    if (! dijit.byId("pausedDateTime").get("value")) {';
        $colScript.='      var curDate = new Date();';
        $colScript.='      dijit.byId("pausedDateTime").set("value", curDate.toISOString().slice(0,10)); ';
        $colScript.='      dijit.byId("pausedDateTimeBis").set("value", curDate.toISOString()); ';
        $colScript.='    }';
      }
      if (property_exists($this, 'paused')) {
        $colScript.='    if (! dijit.byId("paused").get("checked")) {';
        $colScript.='      dijit.byId("paused").set("checked", true);';
        $colScript.='    }';
      }
      $colScript.='  } else {';
      if (property_exists($this, 'pausedDateTime')) {
        $colScript.='    dijit.byId("pausedDateTime").set("value", null); ';
        $colScript.='    dijit.byId("pausedDateTimeBis").set("value", null); ';
      }
      $colScript.='  } ';
      // CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='    formChanged(' . $specificWidgetsToDisabled . ');';
      // Old
      // $colScript .= ' formChanged();';
      // END CHANGE BY Marc TABARY - 2017-03-06 - ALLOW DISABLED SPECIFIC WIDGET
      $colScript.='</script>';
    } else if (pq_substr($colName, -5)=='Local' and property_exists($this, pq_substr($colName, 0, -5))) {
      $globalFld=pq_substr($colName, 0, -5);
      $conversion=$this->getLocalToGlobalConversionRate();
      if (SqlElement::is_a($this, 'PlanningElement')) $globalFld=get_class($this) . '_' . $globalFld;
      $colScript.='<script type="dojo/connect" event="onChange" args="evt">';
      if (self::isPct($colName) or self::isWork($colName)) $colScript.="  dijit.byId('$globalFld').set('value',this.value);";
      else if (self::isDate($colName)) $colScript.="  dijit.byId('$globalFld').set('value',transformDateToSqlDate(this.value));";
      else $colScript.="  var globalValue=calculateAmountFromConvertion(this.value,$conversion,'$globalFld');";
      $colScript.='</script>';
    }

    // Krowry
    if (pq_substr($colName, -9)=="StartDate" or pq_substr($colName, -7)=="EisDate") { // If change start date
      $end=pq_str_replace(array('EisDate', 'StartDate'), array('EndDate', 'EndDate'), $colName);
      $start=$colName;
      if (property_exists($this, $end)) {
        if (self::is_subclass_of($this, 'PlanningElement')) {
          $end=get_class($this) . '_' . $end;
          $start=get_class($this) . '_' . $start;
          $duration=get_class($this) . '_' . pq_str_replace('StartDate', 'Duration', $colName);
        }
        $colScript.='<script type="dojo/connect" event="onChange" args="evt">';
        $colScript.="if(this.value){";
        $colScript.="  var end = dijit.byId('$end');"; // $end will be replaced by value as enclosed by "
        $colScript.="  if(end){";
        $colScript.="    var dtStart = dijit.byId('$start').get('value'); "; // => retrieve date for startDate
        $colScript.="    end.constraints.min=dtStart;"; // Set constraint
        $colScript.="    end.set('dropDownDefaultValue',dtStart);";
        // $colScript .= " if (! end.get('value') ) {";
        // if (!pq_substr($colName, -7)=="EisDate") $colScript .= " end.set('value',dtStart);";
        // if(isset($duration)){
        // $colScript .= " if (dijit.byId('$duration')) {";
        // $colScript .= " dijit.byId('$duration').set('value',1);";
        // $colScript .= " }";
        // }
        // $colScript .= " }";
        $colScript.=" }";
        $colScript.="}";
        $colScript.='</script>';
      }
    }

    return $colScript;
  }

  // ============================================================================**********
  // MISCELLANOUS FUNCTIONS
  // ============================================================================**********

  /**
   * =========================================================================
   * Draw a specific item for a given class.
   * Should always be implemented in the corresponding class.
   * Here is alway an error.
   *
   * @param $item String
   *          the item
   * @return String a message to draw (to echo) : always an error in this class, must be redefined in the inherited class
   */
  public function drawSpecificItem($item) {
    return "No specific item " . $item . " for object " . get_class($this);
  }

  public function drawCalculatedItem($item) {
    return "No calculated item " . $item . " for object " . get_class($this);
  }

  /**
   * =========================================================================
   * Indicate if a property of is translatable
   *
   * @param $col String
   *          the name of the property
   * @return Boolean a boolean
   */
  public function isFieldTranslatable($col) {
    $testField='_is' . pq_ucfirst($col) . 'Translatable';
    if (isset($this->{$testField})) {
      if ($this->{$testField}) {
        return true;
      } else {
        return false;
      }
    }
  }

  /**
   * Determine whether a transition requires a recently created note.
   *
   * The check is deliberately centralised here so status changes made outside
   * the standard interface cannot bypass the rule.
   */
  public static function mustAddNoteOnStatusChange($object, $newStatus=null) {
    if (!$object or !$object->id or !property_exists($object, 'idStatus')) return false;
    $class=get_class($object);
    if ($class=='TicketSimple') $class='Ticket';
    if (!in_array($class, array('Activity','Ticket','Action'))) return false;
    if ($newStatus===null) $newStatus=$object->idStatus;
    if (!$newStatus) return false;
    $old=$object->getOld(true);
    if (!$old or $old->idStatus==$newStatus) return false;
    $typeField=self::getTypeName($class);
    if (!property_exists($object, $typeField) or !$object->$typeField) return false;
    $typeClass=self::getTypeClassName($class);
    $type=new $typeClass($object->$typeField, true);
    if (!$type->mandatoryNoteOnStatusChange or $type->idStatusMandatoryNote!=$newStatus) return false;
    $note=new Note();
    $since=date('Y-m-d H:i:s', time()-300);
    $where='refType='.Sql::str($class).' and refId='.Sql::fmtId($object->id)
        .' and creationDate>='.Sql::str($since);
    return ($note->countSqlElementsFromCriteria(null, $where)==0);
  }

  /**
   * =========================================================================
   * control data corresponding to Model constraints, before saving an object
   *
   * @param
   *          void
   * @return "OK" if controls are good or an error message
   *         must be redefined in the inherited class
   */
  public function control() {
    // traceLog('control (for ' . get_class($this) . ' #' . $this->id . ')');
    global $cronnedScript, $loginSave, $mode, $canForceClose;
    global $parentObject;
    if (sessionValueExists('mailboxImportCronUserId')) {
      $userId=getSessionValue('mailboxImportCronUserId');
      $user=new User($userId);
    } else {
      $user=getSessionUser();
    }
    if (!is_a($this, 'PlanningElement') and !is_a($this, 'WorkElement')) $parentObject=null;
    if (get_class($this)=='History' or get_class($this)=='Mail' or get_class($this)=='Audit') {
      $arrayExtraRequired=array();
      $arrayExtraHidden=array();
    } else {
      $arrayExtraRequired=$this->getExtraRequiredFields();
      $arrayExtraHidden=$this->getExtraHiddenFields();
    }
    $result="";
    $right="";
    // Manage Exceptions
    if (get_class($this)=='Alert' or get_class($this)=='Mail' or get_class($this)=='MailToSend' or get_class($this)=='Subscription' or get_class($this)=='Audit' or get_class($this)=='AuditSummary' or get_class($this)=='ColumnSelector' or get_class($this)=='ProjectSituation' or get_class($this)=='ProjectSituationExpense' or get_class($this)=='ProjectSituationIncome' or SqlElement::$_cancelRecursiveControl==true) {
      $right='YES';
    } else if (isset($cronnedScript) and $cronnedScript==true) { // Cronned script can do everything
      $right='YES';
    } else if (isset($loginSave) and $loginSave==true) { // User->save during autenticate can do everything
      $right='YES';
    } else if (get_class($this)=='User') { // User can change his own data (to be able to change password)
      if (getSessionUser()->id or (getSessionUser()->name and getSessionUser()->isLdap and getSessionUser()->name=$this->name)) {
        $usr=getSessionUser();
        if ($this->id==$usr->id) {
          $changeSensitiveData=false;
          $oldUsr=new User($this->id);
          foreach ($oldUsr as $fld=>$val) {
            if (pq_substr($fld, 0, 1)=='_') continue;
            global $lockPassword;
            if (!$lockPassword and ($fld=='password' or $fld=='salt' or $fld=='crypto' or $fld=='cookieHash' or $fld=='passwordChangeDate' or $fld=='mustChangePassword')) continue;
            if ($oldUsr->$fld!=$this->$fld) {
              $changeSensitiveData=true;
              break;
            }
          }
          if (!$changeSensitiveData) $right='YES';
        }
      }
    } else if (get_class($this)=='Affectation' and property_exists($this, '_automaticCreation') and $this->_automaticCreation) {
      $right='YES';
    }
    if ($right!='YES' and get_class($this)=='Project') {
      if ($this->id) {
        $right=securityGetAccessRightYesNo('menu' . get_class($this), 'update', $this);
      } else {
        $right=securityGetAccessRightYesNo('menu' . get_class($this), 'create');
      }
      if ($right=="YES" and $this->idProject and !$this->id) { // Rights to create projet on a projet
        $proj=new Project($this->idProject, true);
        $right=securityGetAccessRightYesNo('menuProject', 'update', $proj);
      }
      if ($right=="YES" and $this->idProject and $this->id) { // Rights to move from old project
        $old=new Project($this->id, true);
        if ($old->idProject!=$this->idProject) { // Can change project only if has management rights to new one and old one
          $proj=new Project($this->idProject, true);
          $right=securityGetAccessRightYesNo('menuProject', 'update', $proj);
          if ($right=="YES") $right=securityGetAccessRightYesNo('menuProject', 'update', $old);
        }
      }
    } else if ($right!='YES' and get_class($this)=='Affectation') {
      $prj=new Project($this->idProject, true);
      $right=securityGetAccessRightYesNo('menuProject', 'update', $prj);
    } else if ($right!='YES') {
      $right=securityGetAccessRightYesNo('menu' . get_class($this), (($this->id)?'update':'create'), $this, $user);
      if ($right=='YES' and $this->id and property_exists($this, 'idProject')) { // Must check that user also has right to current version of Item
                                                                                 // This is mandatory for API interface, where user can submit change for id on new project also he does not have rights on old project
        $old=$this->getOld(true);
        if ($old->idProject!=$this->idProject) {
          $right=securityGetAccessRightYesNo('menu' . get_class($this), 'update', $old, $user);
        }
      }
    }
    if ($right!='YES') {
      $result.='<br/>' . i18n('error' . (($this->id)?'Update':'Create') . 'Rights');
      $result.=' <span style="font-style:italic">(' . i18n(get_class($this)) . (($this->id)?' #' . $this->id:'') . ')</span>';
      return $result;
    }
    $isCopy=false;
    if (property_exists($this, 'idStatus') and $this->idStatus) {
      $status=new Status($this->idStatus);
      if ($status->isCopyStatus) {
        $isCopy=true;
      }
    }
    $fielMessageExist=false;
    foreach ($this as $col=>$val) {
      $dataType=$this->getDataType($col);
      $dataLength=$this->getDataLength($col);
      if ($col=='idBudgetItem' and $val) {
        $testBudget=new Budget($val, true);
        if ($testBudget->elementary!=1) {
          $result.='<br/>' . i18n('errorNotBudgetItem');
        }
      }
      if (pq_substr($col, 0, 1)!='_') {
        if (pq_ucfirst($col)==$col and is_object($val)) {
          if (!$parentObject) $parentObject=$this;
          $subResult=$val->control();
          if ($subResult!='OK') {
            $result.=$subResult;
          }
        } else {
          // check if required
          if ((pq_strpos($this->getFieldAttributes($col), 'required')!==false or pq_array_key_exists($col, $arrayExtraRequired)) and !$isCopy and !in_array($col, $arrayExtraHidden)) {
            if ($col=='idResource' and !pq_trim($this->idResource) and $user->isResource and Parameter::getGlobalParameter('setResponsibleIfNeeded')!='NO') {
              $this->idResource=$user->id;
              $val=$this->idResource;
            }
            // if ( ( ! $val and $val !== 0) or trim ( $val ) == '') {
            if ((!$val and $val!=='0') or pq_trim($val)=='') { // Since PHP 7.1, all numeric fields have default value zero and cannot be null
              $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption($col)));
              if (!$fielMessageExist) {
                self::addFirstErrorField($this, $col, $result, Parameter::getUserParameter('paramLayoutObjectDetail'), $fielMessageExist);
              }
            }
          }
          if ($val and pq_strpos($this->getFieldAttributes($col), 'unique')!==false) {
            $dataType=$this->getDataType($col);
            if ($dataType=='varchar' or $dataType=='text') {
              $where='UPPER(' . $this->getDatabaseColumnName($col) . ")=" . Sql::str(pq_strtoupper($val));
            } else {
              $where=$this->getDatabaseColumnName($col) . "=" . $val;
            }
            if ($this->id) $where.=" and id<>" . $this->id;
            $count=$this->countSqlElementsFromCriteria(null, $where);
            if ($count>0) {
              $result.='<br/>' . i18n('messageUnique', array($this->getColCaption($col), $val));
            }
          }

          if ($dataType=='datetime'&&$val!=null&&pq_ltrim($val)!='') {
            $d=Security::checkValidDateTime($val, false);
            if (!$d) {
              $result.='<br/>' . i18n('messageDateMandatoryWithTime', array($this->getColCaption($col)));
            }
            // if (pq_strlen ( $val ) == 9) {
            // $result .= '<br/>' . i18n ( 'messageDateMandatoryWithTime', array($this->getColCaption($col)) );
            // }
          }
          if ($dataType=='date' and $val!='' and get_Class($this)!='SubTask') {
            if (pq_strlen($val)!=10 or pq_substr($val, 4, 1)!='-' or pq_substr($val, 7, 1)!='-') {
              $result.='<br/>' . i18n('messageInvalidDateNamed', array($this->getColCaption($col)));
            }
          }
          if ($dataType=='date' and $val!='' and get_Class($this)=='SubTask' and $col==i18n('colDueDate')) {
            if ($val!='null' and pq_strlen($val)!=10 or pq_substr($val, 4, 1)!='-' or pq_substr($val, 7, 1)!='-') {
              $result.='<br/>' . i18n('messageInvalidDateNamed', array($this->getColCaption($col)));
            }
          }
        }
      }
      if ($val and $col!='colRefName') {
        if ($dataType=='varchar') {
          if (pq_mb_strlen($val)>$dataLength) {
            $result.='<br/>' . i18n('messageTextTooLong', array($this->getColCaption($col), $dataLength));
          }
        } else if ($dataType=="int" or $dataType=="decimal") {
          if(pq_trim($val) and $dataType=="int" and $dataLength == 1){
            $val = intval($val);
          }
          if (pq_trim($val) and !is_numeric($val)) {
            $result.='<br/>' . i18n('messageInvalidNumeric', array($this->getColCaption($col) . "='" . $val . "'"));
          }
        }
      }
      if ($dataLength>4000) {
        if ($val=='<div></div>') $val=null;
        try {
          if (isTextFieldHtmlFormatted($val)) $test=strip_tags($val);
        } catch (Exception $e) {
          $result.='<br/>' . i18n('messageInvalidHTML', array($this->getColCaption($col)));
        }
        if (isTextFieldHtmlFormatted($val)) $val=htmlEncode($val, 'formatted'); // Erase <script tags and erase value if messy tags
      }
    }
    // $idType = 'id' . ((get_class ( $this ) == 'TicketSimple') ? 'Ticket' : get_class ( $this )) . 'Type';
    $idType=self::getTypeName(get_class($this));
    if (property_exists($this, $idType)) {
      // $type = ((get_class ( $this ) == 'TicketSimple') ? 'Ticket' : get_class ( $this )) . 'Type';
      $type=self::getTypeClassName(get_class($this));
      $objType=new $type($this->$idType);
      if (self::mustAddNoteOnStatusChange($this)) {
        $result.='<br/>'.i18n('errorMandatoryNoteOnStatusChange');
      }
      if (property_exists($objType, 'mandatoryDescription') and $objType->mandatoryDescription and property_exists($this, 'description')) {
        if (!$this->description) {
          $result=pq_str_replace('<br/>' . i18n('messageMandatory', array($this->getColCaption('description'))), '', $result);
          $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption('description')));
          if (intval(Parameter::getGlobalParameter('logLevel')>=3)) $result.='<br/><span style="font-size:70%">' . $this->getColCaption($idType) . " '" . SqlList::getNameFromId($type, $this->$idType) . "'" . '</span>';
        }
      }
      if (property_exists($objType, 'mandatoryResourceOnHandled') and $objType->mandatoryResourceOnHandled and property_exists($this, 'idResource') and property_exists($this, 'handled')) {
        if ($this->handled and !pq_trim($this->idResource)) {
          if ($user->isResource and Parameter::getGlobalParameter('setResponsibleIfNeeded')!='NO') {
            $this->idResource=$user->id;
          } else {
            $result=pq_str_replace('<br/>' . i18n('messageMandatory', array($this->getColCaption('idResource'))), '', $result);
            $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption('idResource')));
          }
        }
      }
      // ADD qCazelles - Ticket #53
      if (property_exists($objType, 'mandatoryResourceOnHandled') and $objType->mandatoryResourceOnHandled and property_exists($this, 'idResource') and property_exists($this, 'isStarted')) {
        if ($this->isStarted and !pq_trim($this->idResource)) {
          if ($user->isResource and Parameter::getGlobalParameter('setResponsibleIfNeeded')!='NO') {
            $this->idResource=$user->id;
          } else {
            $result=pq_str_replace('<br/>' . i18n('messageMandatory', array($this->getColCaption('idResource'))), '', $result);
            $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption('idResource')));
          }
        }
      }
      // END ADD qCazelles - Ticket #53
      if (property_exists($objType, 'mandatoryResultOnDone') and $objType->mandatoryResultOnDone and property_exists($this, 'result') and property_exists($this, 'done')) {
        if ($this->done and !$this->result) {
          $result=pq_str_replace('<br/>' . i18n('messageMandatory', array($this->getColCaption('result'))), '', $result);
          $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption('result')));
        }
      }
      if (property_exists($objType, 'mandatorySubTaskOnDone') and $objType->mandatorySubTaskOnDone and property_exists($this, '_SubTask') and property_exists($this, 'done')) {
        if ($this->done) {
          $subTask=new SubTask();
          $refType=get_class($this);
          $refId=$this->id;
          $where="refType='$refType' and refId=$refId and done<>1 and idle<>1";
          $asSubTaskListNotDone=$subTask->countSqlElementsFromCriteria(null, $where);
          if ($asSubTaskListNotDone!=0) {
            $result.='<br/>' . i18n('messageMandatorySubTask');
          }
        }
      }
      if (property_exists($objType, 'mandatoryContact') and $objType->mandatoryContact and property_exists($this, 'idContact') and property_exists($this, 'done')) {
        if ($this->done and !$this->idContact) {
          $result=pq_str_replace('<br/>' . i18n('messageMandatory', array($this->getColCaption('idContact'))), '', $result);
          $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption('idContact')));
        }
      }
      if (property_exists($objType, 'mandatoryRecipient') and $objType->mandatoryRecipient and property_exists($this, 'idRecipient') and property_exists($this, 'done')) {
        if ($this->done and !$this->idRecipient) {
          $result=pq_str_replace('<br/>' . i18n('messageMandatory', array($this->getColCaption('idRecipient'))), '', $result);
          $result.='<br/>' . i18n('messageMandatory', array($this->getColCaption('idRecipient')));
        }
      }
    }

    // Gautier #1816
    if (property_exists($this, get_class($this) . 'PlanningElement')) {
      $classe=get_class($this);
      // $classeType = $classe . 'Type';
      $classeType=self::getTypeClassName($classe);
      // $idClasseType = 'id' . $classeType;
      $idClasseType=self::getTypeName($classe);
      $obj=get_class($this) . "PlanningElement";
      $type1=new $classe($this->id, true);
      // passing to done
      $old=$this->getOld();
      if ($this->done and !$old->done) {
        $type2=new $classeType($type1->$idClasseType, true);
        // checkbox lockNoLeftOnDone checked
        if ($type2->lockNoLeftOnDone==1) {
          $pe=new $obj();
          $crit=array('refType'=>$classe, 'refId'=>$this->id);
          $peLst=$pe->getSqlElementsFromCriteria($crit);
          foreach ($peLst as $pe) {
            // left work
            if ($pe->leftWork!=0) {
              // error message
              $result.='<br/>' . i18n("NoLeftOnDone");
            }
          }
        }
      }
    }
    // Particular case for Ticket
    if (property_exists($this, 'WorkElement')) {
      $classe='Ticket';
      $classeType='TicketType';
      $idClasseType='id' . $classeType;
      $obj="WorkElement";
      $type1=new $classe($this->id, true);
      // passing to done
      $old=$this->getOld();
      if ($this->done and !$old->done) {
        $type2=new $classeType($type1->$idClasseType);
        // checkbox lockNoLeftOnDone checked
        if ($type2->lockNoLeftOnDone==1) {
          if ($this->WorkElement and is_object($this->WorkElement) and $this->WorkElement->id) {
            $weLst=array($this->WorkElement);
          } else {
            $we=new WorkElement();
            $crit=array('refType'=>$classe, 'refId'=>$this->id);
            $weLst=$we->getSqlElementsFromCriteria($crit);
          }
          foreach ($weLst as $we) {
            // left work
            if ($we->leftWork!=0) {
              // error message
              $result.='<br/>' . i18n("NoLeftOnDone");
            }
          }
        }
      }
    } // end #1816
      // Control for Closed item that all items are closed
    if (property_exists($this, 'idle') and $this->idle and $this->id) { // #1690 : should be possible to import closed items
      $relationShip=self::$_closeRelationShip;
      if (pq_array_key_exists(get_class($this), $relationShip)) {
        $objects='';
        $error=false;
        // ajout de mehdi
        // ticket #1754
        $canForceClose=false;
        $user=getSessionUser();
        $crit=array('idProfile'=>$user->getProfile($this), 'scope'=>'canForceClose');
        $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
        if ($habil and $habil->id and $habil->rightAccess=='1') {
          $canForceClose=true;
        }
        // end
        foreach ($relationShip[get_class($this)] as $object=>$mode) {
          if ($canForceClose and $mode=='control') {
            $mode="confirm";
          }
          if (($mode=='control' or $mode=='confirm') and property_exists($object, 'idle')) {
            $where=null;
            $obj=new $object();
            $crit=array('id' . get_class($this)=>$this->id, 'idle'=>'0');
            if (property_exists($obj, 'refType') and property_exists($obj, 'refId')) {
              if (property_exists($obj, 'id' . get_class($this))) {
                $crit=null;
                $where="(id" . get_class($this) . "=" . $this->id . " or (refType='" . get_class($this) . "' and refId=" . $this->id . ")) and idle=0";
              } else {
                $crit=array("refType"=>get_class($this), "refId"=>$this->id, "idle"=>'0');
              }
            }
            if ($object=="Dependency") {
              $crit=null;
              $where="idle=0 and ((predecessorRefType='" . get_class($this) . "' and predecessorRefId=" . $this->id . ")" . " or (successorRefType='" . get_class($this) . "' and successorRefId=" . $this->id . "))";
            }
            if ($object=="Link") {
              $crit=null;
              $where="idle=0 and ((ref1Type='" . get_class($this) . "' and ref1Id=" . Sql::fmtId($this->id) . ")" . " or (ref2Type='" . get_class($this) . "' and ref2Id=" . Sql::fmtId($this->id) . "))";
            }
            if (get_class($this)=='ResourceTeam' and get_class($this)!='ResourceTeamAffectation') {
              $crit=array('idResource'=>$this->id);
            }
            $nb=$obj->countSqlElementsFromCriteria($crit, $where);
            if ($nb>0) {
              if ($mode=="control") $error=true;
              if ($mode=="confirm" and self::isSaveConfirmed()) {
                // If mode confirm and message of confirmation occured : OK
              } else {
                $objects.="<br/>&nbsp;-&nbsp;" . i18n($object) . " (" . $nb . ")";
                if ($nb<10) {
                  $objs=$obj->getSqlElementsFromCriteria($crit, false, $where);
                  $objects.=' =>';
                  foreach ($objs as $o) {
                    $objects.=' #' . $o->id;
                  }
                }
              }
            }
          }
        }
        if ($objects!="") {
          if ($error) {
            $result.="<br/>" . i18n("errorControlClose") . $objects;
          } else {
            $result.='<input type="hidden" id="confirmControl" value="save" /><br/>' . i18n("confirmControlSave") . $objects;
          }
        }
      }
    }
    // control Workflow
    $class=get_class($this);
    $old=new $class($this->id, true);
    // $fldType = 'id' . $class . 'Type';
    $fldType=self::getTypeName(get_class($this));

    // When reopening item control that parent is not still closed - PBER : also apply on creation
    if (property_exists($this, 'idle') and $this->idle==0 and (($this->id and $old->idle==1) or !$this->id) and !self::is_a($this, 'PlanningElement') and !self::is_a($this, 'WorkElement')) {
      if (property_exists($this, 'idActivity') and $this->idActivity and $class!='Ticket' and $class!='TicketSimple') {
        $act=new Activity($this->idActivity, true);
        if ($act->idle==1) {
          if ($this->id) $msg="<br/>" . i18n("errorReopenControl", array(i18n('Activity') . ' #' . $this->idActivity));
          else $msg="<br/>" . i18n("errorAddOnClosedItem").'<br/><span style="font-size:80%">'.i18n("Activity"). ' #' . $this->idActivity.'</span>';
          if (pq_strpos($result, $msg)===false) $result.=$msg;
        }
      }
      if (property_exists($this, 'idProject') and $this->idProject) {
        $prj=new Project($this->idProject, true);
        if ($prj->idle==1 and ! SqlElement::$_copyInProgress) {
          if ($this->id) $msg="<br/>" . i18n("errorReopenControl", array(i18n('Project') . ' #' . $this->idProject));
          else $msg="<br/>" . i18n("errorAddOnClosedItem").'<br/><span style="font-size:80%">'.i18n("Project"). ' #' . $this->idProject.'</span>';
          if (pq_strpos($result, $msg)===false) $result.=$msg;
        }
      }
    }

    // Control Workflow
    if (self::$_skipWorkflowControl==false and property_exists($class, 'idStatus') and property_exists($class, $fldType) and pq_trim($old->idStatus) and pq_trim($old->$fldType) and (pq_trim($old->idStatus)!=pq_trim($this->idStatus) or pq_trim($old->$fldType)!=pq_trim($this->$fldType)) and $old->id and $class!='Document') {
      $oldStat=new Status($old->idStatus);
      $statList=SqlList::getList('Status');
      $firstStat=key($statList);
      if (!$oldStat->isCopyStatus and ($this->idStatus!=$old->idStatus or $this->idStatus!=$firstStat)) {
        $idProfile=getSessionUser()->getProfile($this);
        // ELIOTT - LEAVE SYSTEM
        // In fact, leaveType and EmploymentContractType aren't standarts Type. They are objects in model/
        if ($fldType==="idLeaveType") {
          $type=new LeaveType($this->$fldType);
        } else if ($fldType==="idEmploymentContractType") {
          $type=new EmploymentContractType($this->$fldType);
        } else {
          $type=new Type($this->$fldType);
        }
        // For Leave System and Leave :
        // - Leave Admin or
        // - Manager of Employee or
        // - Employee of the leave
        // can see status
        if (isLeavesSystemActiv() and $class=='Leave') {
          if (isLeavesAdmin() or isManagerOfEmployee(getSessionUser()->id, $this->idEmployee) or (getSessionUser()->isEmployee==1 and $this->idEmployee==getSessionUser()->id)) {
            $theProfile=getFirstADMProfile();
            if ($theProfile!=null) {
              $idProfile=$theProfile->id;
            }
          }
        }
        // ELIOTT - LEAVE SYSTEM

        $crit=array('idWorkflow'=>$type->idWorkflow, 'idStatusTo'=>$this->idStatus, 'idProfile'=>$idProfile);
        if (pq_trim($old->idStatus)!=pq_trim($this->idStatus)) {
          $crit['idStatusFrom']=$old->idStatus;
        }
        $ws=new WorkflowStatus();
        $wsList=$ws->getSqlElementsFromCriteria($crit);
        $allowed=false;
        foreach ($wsList as $ws) {
          // MTY - LEAVE SYSTEM
          // For Leave System and Leave :
          // - Employee of the leave
          // status that has not id = 1 and with setSubmittedLeave = 0 and setAcceptedLeave = 1 or setRejectedLeave = 1
          // are not allowed
          if (isLeavesSystemActiv() and $class=='Leave' and $ws->id!=1) {
            if (getSessionUser()->isEmployee==1 and $this->idEmployee==getSessionUser()->id) {
              $theStatus=new Status($ws->id);
              if ($theStatus->setSubmittedLeave==0 and ($theStatus->setRejectedLeave==1 or $theStatus->setAcceptedLeave==1)) {
                $ws->allowed=false;
              }
            }
          }
          // MTY - LEAVE SYSTEM
          if ($ws->allowed) {
            $allowed=true;
            break;
          }
        }
        if (!$allowed) {
          $result.="<br/>" . i18n("errorWorflow");
        }
      }
    }
    $isChecklistable=SqlElement::getSingleSqlElementFromCriteria('Checklistable', array('name'=>$class));
    if (Module::isModuleActive('moduleChecklist') and $isChecklistable->id!='' and property_exists($class, 'idStatus')) {
      $status=new Status($this->idStatus);
      if ($status->setDoneStatus) {
        $done='on';
        $crit="nameChecklistable='" . $class . "' and idle=0";
        if (property_exists($this, $fldType)) {
          $crit.=' and (idType is null ';
          if ($this->$fldType) {
            $crit.=" or idType=" . $this->$fldType;
          }
          $crit.=')';
        }
        $cd=new ChecklistDefinition();
        $cdList=$cd->getSqlElementsFromCriteria(null, false, $crit);
        foreach ($cdList as $cDf) {
          $idStatus=$this->idStatus;
          $checklistDefinitionId=$cDf->id;
          $checklistObjectClass=$class;
          $checklistObjectId=$this->id;
          if (file_exists("../tool/controlChecklist.php")) include "../tool/controlChecklist.php";
        }
      }
    }
    // PBER : on project change (or on type change through multiple update), check that selected type fits the restriction (if any)
    if (property_exists($this, $fldType) and property_exists($this, 'idProject') and get_class($this)!='Project' and ($this->idProject!=$old->idProject or $this->$fldType!=$old->$fldType)) {
      $newProject=new Project($this->idProject, true);
      $oldProject=new Project($old->idProject, true);
      if ($newProject->idProjectType!=$oldProject->idProjectType or $this->$fldType!=$old->$fldType) {
        $typeClass=self::getTypeClassName(get_class($this));
        $crit=array('idProjectType'=>$newProject->idProjectType, 'className'=>$typeClass);
        $restrictList=SqlList::getListWithCrit('RestrictType', $crit, 'idType');
        if (count($restrictList)>0 and ! in_array($this->$fldType,$restrictList)) {
          $result .= "<br/>" . i18n ( "errorTypeRestricted" )
          .'<br/><span style="font-size:80%">'.i18n(get_class($this)). ' - '.i18n('Type').' "'.SqlList::getNameFromId('Type', $this->$fldType).'"'
              .' | '.i18n('Project'). ' - '.i18n('Type').' "'.SqlList::getNameFromId('Type', $newProject->idProjectType).'"</span>';
        } else {
          $crit=array('idProject'=>$newProject->id, 'className'=>$typeClass);
          $restrictList=SqlList::getListWithCrit('RestrictType',$crit,'idType');
          if (count($restrictList)>0 and ! in_array($this->$fldType,$restrictList)) {
            $result .= "<br/>" . i18n ( "errorTypeRestricted" )
            .'<br/><span style="font-size:80%">'.i18n(get_class($this)).' - '.i18n('Type').' "'.SqlList::getNameFromId('Type', $this->$fldType).'"'
                .' | '.i18n('Project').' #'.$newProject->id. ' - '.i18n('Type').' "'.SqlList::getNameFromId('Type', $newProject->idProjectType).'"</span>';
          }
        }
      }
    }

    // tags #10722
    if (property_exists($this, 'tags') and $this->tags and $this->tags!=$old->tags) {
      $myTags=explode('#', $this->tags);
      $errors=[];

      foreach ($myTags as $tag) {
        $tag=trim($tag);
        if ($tag==="") continue;

        if (!preg_match('/^[a-z0-9]+$/', $tag)) {
          $errors[]=$tag;
        }
      }

      if (!empty($errors)) {
        $msgError=implode(', ', $errors);
        $result.="<br/>" . i18n("errorFormatTags", array($msgError));
      }
    }

    // PlugIn Management
    $list=Plugin::getEventScripts('control', get_class($this));
    foreach ($list as $idScript=>$script) {
      require $script; // execute code
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }

  /**
   * =========================================================================
   * control data corresponding to Model constraints, before deleting an object
   *
   * @param
   *          void
   * @return "OK" if controls are good or an error message
   *         must be redefined in the inherited class
   */
  public function deleteControl() {
    $result="";
    $objects="";
    $realWorks="";
    $plannedWorks="";
    $right=securityGetAccessRightYesNo('menu' . get_class($this), 'delete', $this);
    if (get_class($this)=='Alert' or get_class($this)=='Mail' or get_class($this)=='MailToSend' or get_class($this)=='Subscription' or get_class($this)=='Audit' or get_class($this)=='AuditSummary' or get_class($this)=='ColumnSelector' or get_class($this)=='ProjectSituation' or get_class($this)=='ProjectSituationExpense' or get_class($this)=='ProjectSituationIncome') {
      $right='YES';
    }
    if ($right!='YES') {
      $result.='<br/>' . i18n('errorDeleteRights');
      $result.=' <span style="font-style:italic">(' . i18n(get_class($this)) . ' #' . $this->id . ')</span>';
      return $result;
    }
    $relationShip=self::$_relationShip;
    $canForceDelete=false;
    $canDeleteRealWork=false;
    if (getSessionUser()->id) {
      $user=getSessionUser();
      $crit=array('idProfile'=>$user->getProfile($this), 'scope'=>'canForceDelete');
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
      if ($habil and $habil->id and $habil->rightAccess=='1') {
        $canForceDelete=true;
      }
      $crit=array('idProfile'=>$user->getProfile($this), 'scope'=>'canDeleteRealWork');
      $habil=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', $crit);
      if ($habil and $habil->id and $habil->rightAccess=='1') {
        $canDeleteRealWork=true;
      }
    }
    if (pq_array_key_exists(get_class($this), $relationShip)) {
      $relations=$relationShip[get_class($this)];
      $error=false;
      foreach ($relations as $object=>$mode) {
        if ($mode=="control" and ($canForceDelete or $canDeleteRealWork)) {
          $mode="confirm";
        } else if ($mode=="controlStrict" and !$canDeleteRealWork) {
          $mode="control";
        }
        if ($mode=="control" or $mode=="confirm") {
          $where=null;
          $obj=new $object();
          $crit=array('id' . get_class($this)=>$this->id);
          if (get_class($this)=='AccessProfileNoProject') {
            $crit=array('idAccessProfile'=>$this->id);
          }
          if (self::is_a($this, 'Version')) {
            $crit=null;
            $where="(1=0";
            $arrayVersion=array(
                'idVersion',
                'idTargetVersion',
                'idTargetProductVersion',
                'idTargetComponentVersion',
                'idOriginalVersion',
                'idOriginalProductVersion',
                'idOriginalComponentVersion');
            foreach ($arrayVersion as $vers) {
              if (property_exists($obj, $vers)) {
                $where.=" or " . $obj->getDatabaseColumnName($vers) . "=" . $this->id;
              }
            }
            $where.=")";
          } else if (property_exists($obj, 'refType') and property_exists($obj, 'refId')) {
            if (property_exists($obj, 'id' . get_class($this))) {
              $crit=null;
              $where="id" . get_class($this) . "=" . $this->id . " or (refType='" . get_class($this) . "' and refId=" . $this->id . ")";
            } else {
              $crit=array("refType"=>get_class($this), "refId"=>$this->id);
            }
          }
          if ($object=="Dependency") {
            $crit=null;
            $where="(predecessorRefType='" . get_class($this) . "' and predecessorRefId=" . $this->id . ")" . " or (successorRefType='" . get_class($this) . "' and successorRefId=" . $this->id . ")";
          } else if ($object=="Link") {
            $crit=null;
            $where="(ref1Type='" . get_class($this) . "' and ref1Id=" . Sql::fmtId($this->id) . ")" . " or (ref2Type='" . get_class($this) . "' and ref2Id=" . Sql::fmtId($this->id) . ")";
          } else if (pq_substr($object, -4)=='Type' and property_exists($object, 'scope')) {
            $scope=pq_substr($object, 0, pq_strlen($object)-4);
            $crit['scope']=$scope;
          } else if ($object=="Assignment" and isLeavesSystemActiv()) {
            $crit=null;
            $act=new Activity();
            $actTable=$act->getDatabaseTableName();
            $leaveProject=Project::getLeaveProjectId();
            $where="( idResource=$this->id and (refType, refId) not in (select 'Activity', id from $actTable where idProject=$leaveProject) )";
          }
          if (get_class($this)=='ResourceTeam') {
            $crit=array('idResource'=>$this->id);
          }
          $nb=$obj->countSqlElementsFromCriteria($crit, $where);
          if ($nb>0) {
            if ($mode=="control") $error=true;
            if ($mode=="confirm" and self::isDeleteConfirmed()) {
              // If mode confirm and message of confirmation occured : OK
            } else {
              $objects.="<br/>&nbsp;-&nbsp;" . i18n($object) . " (" . $nb . ")";
              if (property_exists(get_class($this), get_class($this) . 'PlanningElement')) {
                $ple=get_class($this) . 'PlanningElement';
                $planningMode=new PlanningMode($this->$ple->idPlanningMode);
                if ($planningMode->code=='MAN' and $this->$ple->plannedWork) {
                  $plannedWorks.="<br/>&nbsp;-&nbsp;" . i18n($this->$ple->refType) . " #" . $this->$ple->refId . " (" . Work::displayWorkWithUnit($this->$ple->plannedWork) . ")";
                }
              }
            }
          }
          if ($canDeleteRealWork) {
            $objList=$obj->getSqlElementsFromCriteria($crit, null, $where);
            foreach ($objList as $objWork) {
              $work=new Work();
              $refType=get_class($objWork);
              $refId=$objWork->id;
              $critWork=array('refType'=>$refType, 'refId'=>$refId);
              $workList=$work->getSqlElementsFromCriteria($critWork);
              foreach ($workList as $work) {
                $realWorks.="<br/>&nbsp;-&nbsp;" . i18n('realWorkElement', array(
                    i18n($work->refType) . ' #' . $refId,
                    SqlList::getNameFromId('Resource', $work->idResource),
                    $work->displayWorkWithUnit($work->work),
                    htmlFormatDate($work->workDate, true)));
              }
            }
          }
          if (get_class($this)=='Contact' and property_exists($obj, 'idSponsor')) {
            // Also search for sponsor
            $crit=array('idSponsor'=>$this->id);
            $nb=$obj->countSqlElementsFromCriteria($crit, $where);
            if ($nb>0) {
              if ($mode=="control") $error=true;
              if ($mode=="confirm" and self::isDeleteConfirmed()) {
                // If mode confirm and message of confirmation occured : OK
              } else {
                $objects.="<br/>&nbsp;-&nbsp;" . i18n($object) . " (" . $nb . ")";
              }
            }
          }
        }
      }
      if ($objects!="") {
        if ($error) {
          $result.="<br/>" . i18n("errorControlDelete") . $objects;
        } else {
          $result.='<input type="hidden" id="confirmControl" value="delete" /><br/>' . i18n("confirmControlDelete") . $objects;
          if ($canDeleteRealWork) {
            $result.="<br/><br/>" . i18n("confirmControlDeleteRealWork") . $realWorks;
          }
          if ($plannedWorks) {
            $result.="<br/><br/>" . i18n("confirmControlDeletePlannedWork") . $plannedWorks;
          }
        }
      }
    }
    if (!self::isDeleteConfirmed() and property_exists($this, 'idProject') and property_exists($this, 'idStatus')) {
      $syncItem=SynchronizedItems::getSynchronizedItemKey(get_class($this), $this->id);
      if ($syncItem!=null) {
        // Delete existing synchonizedItems when one of then is deleted
        if (pq_strpos($result, 'id="confirmControl" value="delete"')===false) $result.='<input type="hidden" id="confirmControl" value="delete" />';
        $split=pq_explode('#', $syncItem);
        $result.="<br/><br/>" . i18n("confirmDeleteSynchronizedItem", array(i18n($split[0]), $split[1]));
      }
    }
    // PlugIn Management
    $list=Plugin::getEventScripts('deleteControl', get_class($this));
    foreach ($list as $idScript=>$script) {
      require $script; // execute code
    }
    if ($result=="") {
      $result='OK';
    }
    return $result;
  }

  /**
   * =========================================================================
   * Return the menu string for the object (from its class)
   *
   * @return String a string
   */
  public function getMenuClass() {
    if (get_class($this)=='ProductProject' or get_class($this)=='VersionProject') return 'menuProject';
    return "menu" . get_class($this);
  }

  /**
   * =========================================================================
   * Send a mail on status change (if object is "mailable")
   *
   * @param
   *          void
   * @return status of mail, if sent
   */
  public function sendMailIfMailable($newItem=false, $statusChange=false, $directStatusMail=null, $responsibleChange=false, $noteAdd=false, $attachmentAdd=false, $noteChange=false, $descriptionChange=false, $resultChange=false, $assignmentAdd=false, $assignmentChange=false, $anyChange=false, $affectationAdd=false, $affectationChange=false, $linkAdd=false, $linkDelete=false, $attachments=false, $priorityChange=false, $newUserCreated=false) {
    global $cronnedScript, $doNotTriggerAlerts;
    $this->sendAlertNotification($newItem, $statusChange, $directStatusMail, $responsibleChange, $noteAdd, $attachmentAdd, $noteChange, $descriptionChange, $resultChange, $assignmentAdd, $assignmentChange, $anyChange, $affectationAdd, $affectationChange, $linkAdd, $linkDelete, $attachments, $priorityChange, $newUserCreated);
    if ($doNotTriggerAlerts==true) return false;
    $objectClass=get_class($this);
    $idProject=($objectClass=='Project')?$this->id:((property_exists($this, 'idProject'))?$this->idProject:null);
    if ($objectClass=='TicketSimple') {
      $objectClass='Ticket';
    }
    if (($objectClass=='Resource' or $objectClass=='Contact') and $newUserCreated) $objectClass='User';
    if ($objectClass=='History' or $objectClass=='Audit' or $objectClass=='KpiHistory' or !in_array($objectClass, SqlList::getListNotTranslated('Mailable'))) {
      return false; // exit : not for History
    }

    $canBeSend=true;
    if ($idProject) {
      $canBeSend=!SqlList::getFieldFromId("Project", $idProject, "isUnderConstruction");
    }
    // KROWRY
    $statusMailList=array();
    $statusMailListOrganized=array();
    $statusMail=new StatusMail();
    $sender=Parameter::getGlobalParameter('paramMailSender');

    if ($directStatusMail) { // Direct Send Mail
      $statusMailList=array($directStatusMail);
      $statusMailListOrganized=$statusMailList;
      if (getSessionUser()->email) $sender=getSessionUser()->email;
    } else if ($canBeSend) {
      if ($objectClass=='Affectation') {
        $mailable=SqlElement::getSingleSqlElementFromCriteria('Mailable', array('name'=>'Project'));
      } else {
        $mailable=SqlElement::getSingleSqlElementFromCriteria('Mailable', array('name'=>$objectClass));
      }
      if (!$mailable or !$mailable->id) {
        return false; // exit if not mailable object
      }
      $crit="idle=0";
      $crit.=" and idMailable=" . $mailable->id . " and ( 1=0 ";
      if ($statusChange and property_exists($this, 'idStatus') and pq_trim($this->idStatus)) {
        $any=SqlElement::getSingleSqlElementFromCriteria('EventForMail', array('name'=>'statusChange'));
        $crit.="  or idStatus=" . $this->idStatus . " or idEventForMail=" . $any->id . " ";
      }
      if ($responsibleChange) {
        $crit.=" or idEventForMail=1 ";
      }
      if ($noteAdd) {
        $crit.=" or idEventForMail=2 ";
      }
      if ($attachmentAdd) {
        $crit.=" or idEventForMail=3 ";
      }
      if ($noteChange) {
        $crit.=" or idEventForMail=4 ";
      }
      if ($descriptionChange) {
        $crit.=" or idEventForMail=5 ";
      }
      if ($resultChange) {
        $crit.=" or idEventForMail=6 ";
      }
      if ($assignmentAdd) {
        $crit.=" or idEventForMail=7 ";
      }
      if ($assignmentChange) {
        $crit.=" or idEventForMail=8 ";
      }
      if ($anyChange) {
        $crit.=" or idEventForMail=9 ";
      }
      if ($affectationAdd) {
        $crit.=" or idEventForMail=10 ";
      }
      if ($affectationChange) {
        $crit.=" or idEventForMail=11 ";
      }
      if ($linkAdd) {
        $crit.=" or idEventForMail=12 ";
      }
      if ($linkDelete) {
        $crit.=" or idEventForMail=13 ";
      }
      if ($statusChange) {
        $crit.=" or idEventForMail=14 ";
      }
      if ($priorityChange) {
        $crit.=" or idEventForMail=15 ";
      }
      if ($newUserCreated) {
        $crit.=" or idEventForMail=16 ";
      }
      $crit.=")";
      $statusMailList=$statusMail->getSqlElementsFromCriteria(null, false, $crit);
      // $statusMailList contains all events compatible with current change.
      // Now, we must resctrict : if several lines exist for same event, we must limit to 1 only (depending on project and/or type
      // $typeName='id'.$objectClass.'Type';
      $typeName=SqlElement::getTypeName($objectClass);
      $proj=null;
      $type=null;
      if (property_exists($this, "idProject")) {
        $proj=($objectClass=='Project')?$this->id:$this->idProject;
        $project=new Project($proj, true);
        $topList=$project->getTopProjectList(true);
      }
      if (property_exists($this, $typeName)) {
        $type=$this->$typeName;
      }
      $isSubProj=false;
      foreach ($statusMailList as $stm) {
        $isSubProj=false;
        if ($proj and $stm->idProject) {
          if (in_array($stm->idProject, $topList)) {
            // $statusMailListOrganized[$stm->idEventForMail]=$stm;
            $isSubProj=true;
          }
        }
        if ($proj and $stm->idProject and $stm->idProject!=$proj and !$isSubProj) { // Does not concern current project, must not apply
          continue;
        }
        if ($type and $stm->idType and $stm->idType!=$type) { // Does not concern current type, must not apply
          continue;
        }
        if (!$stm->idEventForMail) $stm->idEventForMail=0;
        ;
        if (!isset($statusMailListOrganized[$stm->idEventForMail])) { // No other already selected : OK
          $statusMailListOrganized[$stm->idEventForMail]=$stm;
          continue;
        }
        // Now we are treating duplicates (already exists for event, we have another one that may fit, so we must select on Project and / or Type
        if ($proj and $stm->idProject and ($stm->idProject==$proj or $isSubProj)) { // OK, dedicated to correct project (or top one)
          if (!$statusMailListOrganized[$stm->idEventForMail]->idProject) {
            $statusMailListOrganized[$stm->idEventForMail]=$stm; // Found rule on projet, previous was not
          } else if (array_search($stm->idProject, $topList)<array_search($statusMailListOrganized[$stm->idEventForMail]->idProject, $topList)) {
            $statusMailListOrganized[$stm->idEventForMail]=$stm; // Found rule with projet "neared" on parents list than previously stored
          } else if ($stm->idProject and array_search($stm->idProject, $topList)>array_search($statusMailListOrganized[$stm->idEventForMail]->idProject, $topList)) {
            continue; // Found rule with projet "farther" on parents list than previously stored
          } else if ($type and $stm->idType and $stm->idType==$type) {
            $statusMailListOrganized[$stm->idEventForMail]=$stm; // Same project than previously stored and type match : this is this one !!!!
          } else {
            continue; // Same project than previously stored and not type match : pass ! (duplicate ?)
          }
        } else { // Not project defined rule, will check on type
          if ($type and $stm->idType and $stm->idType==$type) { // Same type but not same project, replace if previous not on project
            if (!isset($statusMailListOrganized[$stm->idEventForMail]) or !$statusMailListOrganized[$stm->idEventForMail]->idProject) {
              $statusMailListOrganized[$stm->idEventForMail]=$stm; // Same type and previously stored not on project neither : store
            } else {
              continue; // Not same Same project than previously stored and not type match : pass ! (duplicate ?)
            }
          }
        }
      }
    }
    if (count($statusMailListOrganized)==0||(!$directStatusMail&&!$canBeSend)) {
      return false; // exit not a status for mail sending (or disabled)
    }
    // BEGIN modif gmartin / handle Email templates Ticket #157
    $destTab=array('basic'=>null); // store the mail adressses and the templates names that will be used to send the mails. replace : $dest
    $emailTemplateTab=array();
    $i=0;
    foreach ($statusMailListOrganized as $statusMail) {
      $emailTemplateTab[$i]=new EmailTemplate($statusMail->idEmailTemplate);
      if ($emailTemplateTab[$i]->name==null) {
        $emailTemplateTab[$i]->name='basic';
        $emailTemplateTab[$i]->id='0';
      }
      $destTab[$emailTemplateTab[$i]->id]=null;

      if ($statusMail->idType) {
        if (property_exists($this, 'idType') and $this->idType!=$statusMail->idType) {
          continue; // exist : not corresponding type
        }
        // $typeName = 'id' . $objectClass . 'Type';
        $typeName=SqlElement::getTypeName($objectClass);
        if (property_exists($this, $typeName) and $this->$typeName!=$statusMail->idType) {
          continue; // exist : not corresponding type
        }
      }
      if ($statusMail->mailToUser==0 and $statusMail->mailToContact==0 and $statusMail->mailToAccountable==0 and $statusMail->mailToResource==0 and $statusMail->mailToProject==0 and $statusMail->mailToProjectIncludingParentProject==0 and $statusMail->mailToLeader==0 and $statusMail->mailToManager==0 and $statusMail->mailToSponsor==0 and $statusMail->mailToFinancialResponsible==0 and $statusMail->mailToOther==0 and $statusMail->mailToSubscribers==0 and $statusMail->mailToAssigned==0 and empty($statusMail->mailToselectedReceivers)) {
        continue; // exit not a status for mail sending (or disabled)
      }
      if ($statusMail->mailToUser) {
        if (property_exists($this, 'idUser')) {
          $user=new User($this->idUser, true);
          $newDest="###" . $user->email . "###";
          if ((!$user->idle or $user->dummy) and $user->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToAccountable) {
        if (property_exists($this, 'idAccountable')) {
          $resource=new Resource($this->idAccountable, true);
          $newDest="###" . $resource->email . "###";
          if (!$resource->idle and $resource->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToResource) {
        if (property_exists($this, 'idResource')) {
          $resource=new Resource($this->idResource, true);
          $newDest="###" . $resource->email . "###";
          if (!$resource->idle and $resource->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToSponsor) {
        if (property_exists($this, 'idSponsor')) {
          $sponsor=new Sponsor($this->idSponsor, true);
          $newDest="###" . $sponsor->email . "###";
          if (!$sponsor->idle and $sponsor->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToProject or $statusMail->mailToLeader or $statusMail->mailToProjectIncludingParentProject) {
        $aff=new Affectation();
        if ($statusMail->mailToProjectIncludingParentProject) {
          $proj=new Project($idProject, true);
          $critWhere="idle=0 and idProject in " . transformValueListIntoInClause($proj->getTopProjectList(true));
          $affList=$aff->getSqlElementsFromCriteria(null, false, $critWhere);
        } else {
          $crit=array('idProject'=>$idProject, 'idle'=>'0');
          $affList=$aff->getSqlElementsFromCriteria($crit, false);
        }
        if ($affList and count($affList)>0) {
          foreach ($affList as $aff) {
            $resource=new Affectable($aff->idResource, true);
            if ($statusMail->mailToProject or $statusMail->mailToProjectIncludingParentProject) {
              // Change on V4.4.0 oly send mail if user has read access to item
              if ($aff->idResource==getSessionUser()->id) {
                $usr=getSessionUser();
              } else {
                $usr=new User($aff->idResource, true);
              }
              if (!$resource->idle and !$resource->dontReceiveTeamMails) {
                $newDest="###" . $resource->email . "###";
                if ($resource->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
                  $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
                  $destTab[$emailTemplateTab[$i]->id].=$newDest;
                }
              }
            }
            if ($statusMail->mailToLeader and ($aff->idProfile or $resource->idProfile)) {
              $profile=($aff->idProfile)?$aff->idProfile:$resource->idProfile;
              $prf=new Profile($profile);
              if ($prf->profileCode=='PL') {
                $newDest="###" . $resource->email . "###";
                if (!$resource->idle and $resource->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
                  $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
                  $destTab[$emailTemplateTab[$i]->id].=$newDest;
                }
              }
            }
          }
        }
      }
      if ($statusMail->mailToManager) {
        if (property_exists($this, 'idProject')) {
          $project=new Project($idProject, true);
          $manager=new Affectable($project->idResource, true);
          $newDest="###" . $manager->email . "###";
          if (!$manager->idle and $manager->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToAssigned) {
        $ass=new Assignment();
        $crit=array('refType'=>$objectClass, 'refId'=>$this->id);
        $assList=$ass->getSqlElementsFromCriteria($crit);
        foreach ($assList as $ass) {
          $res=new ResourceAll($ass->idResource, true);
          $newDest="###" . $res->email . "###";
          if (!$res->idle and $res->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToContact) {
        if (property_exists($this, 'idContact')) {
          $contact=new Contact($this->idContact, true);
          $newDest="###" . $contact->email . "###";
          if (!$contact->idle and $contact->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToSubscribers) {
        $crit="(refType='" . $objectClass . "' and refId=" . Sql::fmtId($this->id) . ")";
        if (property_exists($this, 'idProject')) {
          $crit.=" or (refType='Project' and refId=" . Sql::fmtId($this->idProject) . ")";
        }
        $sub=new Subscription();
        $lstSub=$sub->getSqlElementsFromCriteria(null, null, $crit);
        foreach ($lstSub as $sub) {
          $resource=new Affectable($sub->idAffectable, true);
          $newDest="###" . $resource->email . "###";
          if ((!$resource->idle or $resource->dummy) and $resource->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToFinancialResponsible) {
        if (property_exists($this, 'idResponsible')) {
          $responsible=new Resource($this->idResponsible);
          $newDest="###" . $responsible->email . "###";
          if (!$responsible->idle and $responsible->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->mailToOther) {
        if ($statusMail->otherMail) {
          $otherMail=pq_str_replace(';', ',', $statusMail->otherMail);
          $otherMail=pq_str_replace(' ', ',', $otherMail);
          $split=pq_explode(',', $otherMail);
          foreach ($split as $adr) {
            if ($adr and $adr!='') {
              $newDest="###" . $adr . "###";
              if (pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
                $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
                $destTab[$emailTemplateTab[$i]->id].=$newDest;
              }
            }
          }
        }
      }
      if ($statusMail->mailToselectedReceivers) {
        $emails=explode('##', $statusMail->mailToselectedReceivers);
        $noDuplicateEmails=[];
        foreach ($emails as $email) {
          $email=strtolower(trim($email));
          if (!in_array($email, $noDuplicateEmails)) {
            $noDuplicateEmails[]=$email;
          }
        }
        foreach ($noDuplicateEmails as $email) {
          $newDest="###" . $email . "###";
          if (pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      $i++;
    }

    $msgWithoutDest=0; // check if something went wrong in retreiving email adresses
    $j=$i;
    while ($i--) {
      if ($destTab[$emailTemplateTab[$i]->id]=='' or $destTab[$emailTemplateTab[$i]->id]==null or pq_str_replace(array(',', ';', ' '), '', $destTab[$emailTemplateTab[$i]->id])=='') $msgWithoutDest++;
      else $destTab[$emailTemplateTab[$i]->id]=pq_str_replace('###', '', $destTab[$emailTemplateTab[$i]->id]);
    }

    if ($j<=$msgWithoutDest) {
      traceLog('sendMailIfMailable : Mails without dest');
      return false; // exit because no adresses
    }
    // END modif gmartin Ticket #157
    if ($newUserCreated) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNewUserCreated');
    } else if ($newItem) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNew');
    } else if ($noteAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNote');
    } else if ($noteChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNoteChange');
    } else if ($assignmentAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAssignment');
    } else if ($assignmentChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAssignmentChange');
    } else if ($attachmentAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAttachment');
    } else if ($statusChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleStatus');
    } else if ($responsibleChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleResponsible');
    } else if ($priorityChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitlePriorityChanged');
    } else if ($descriptionChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleDescription');
    } else if ($resultChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleResult');
    } else if ($directStatusMail) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleDirect');
    } else if ($anyChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAnyChange');
    } else if ($affectationAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAffectationAdd');
    } else if ($affectationChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAffectationChange');
    } else if ($linkAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleLinkAdd');
    } else if ($linkDelete) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleLinkDelete');
    } else {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitle'); // default
    }
    $title=$this->parseMailMessage('[' . $objectClass . ' #' . $this->id . ']' . $paramMailTitle);
    $references=$objectClass . "-" . $this->id;
    $message=$this->getMailDetail();
    if ($directStatusMail and isset($directStatusMail->message) and pq_trim($directStatusMail->message)!='') {
      // $emailTemplateTab[0]->template = $this->getMailDetail($directStatusMail->message);
      $emailTemplateTab[0]->template=$this->parseMailMessage($directStatusMail->message) . '<br/><br/>' . $emailTemplateTab[0]->template;
    }
    // BEGIN add gmartin Ticket #157
    $groupMails=Parameter::getGlobalParameter('mailGroupActive');
    if ($directStatusMail) $groupMails='NO';
    $resultMail=array();
    $sentArray=array();
    while ($j--) {
      if ($groupMails=='YES') {
        $temp=new MailToSend();
        $temp->idUser=getCurrentUserId();
        $temp->refType=$objectClass;
        $temp->refId=$this->id;
        $temp->idEmailTemplate=$emailTemplateTab[$j]->id;
        $temp->template=$emailTemplateTab[$j]->name;
        if ($emailTemplateTab[$j]->title) {
          $temp->title=$this->getMailDetailFromTemplate($emailTemplateTab[$j]->title, null, true);
        } else {
          $temp->title=$title;
        }
        $temp->dest=$destTab[$emailTemplateTab[$j]->id];
        if (Parameter::getUserParameter('notReceiveHisOwnEmails')=='YES' and !$cronnedScript) {
          $tabDest=pq_explode(",", $temp->dest);
          if (count($tabDest)>0) {
            $curUser=new Affectable(getSessionUser()->id, true);
            foreach ($tabDest as $id=>$mail) {
              if (pq_trim($mail)==$curUser->email) {
                unset($tabDest[$id]);
              }
            }
          }
          $temp->dest=implode(",", $tabDest);
        }
        $temp->recordDateTime=date('Y-m-d H:i:s');
        if (pq_trim(pq_str_replace(array(',', ';', ' '), '', $temp->dest))) {
          $tempRes=$temp->save();
          $resultMail[]='TEMP';
        }
      } else {
        $tempAttach='No';
        $erroSize='';
        // florent ticket 4442
        $directory=Parameter::getGlobalParameter('paramAttachmentDirectory');
        $lstAtt=array();
        $addAttachToMessage='';
        $notFound=' not found ';
        if (!empty($attachments) and Parameter::getGlobalParameter('paramMailerType')=='phpmailer') {
          $c=0;
          $addAttachToMessage="<table style='font-size:11pt;min-width: 800px; max-width: 1200px; width:95%;font-family:Verdana,Arial,Helvetica,sans-serif;'>
                                <tr><td colspan='3' style='background:#606062;color:#ffffff;text-align:center;font-size:14pt;font-weight:normal;width:100%'><div >" . htmlEncode(i18n('fileAttachment')) . "</div></td></tr>";
          foreach ($attachments as $val) {
            $c++;
            $addAttachToMessage.="<tr><td colspan='2' style='background:#ffffff;font-weight:bold;text-align:right;width:30%;min-width:30%;vertical-align:top;white-space:nowrap;padding-bottom:10px;'><div>" . i18n('col' . pq_ucfirst($val[1])) . "</div></td>";
            if ($val[1]=='file') {
              if (isset($val[2])) {
                $attachmentDirectory=Parameter::getGlobalParameter('paramAttachmentDirectory');
                $pathSeparator=Parameter::getGlobalParameter('paramPathSeparator');
                $folderPath=$attachmentDirectory . $pathSeparator . "attachment_" . $val[2] . "_" . $val[0] . $pathSeparator;
                $files=scandir($folderPath);
                foreach ($files as $file) {
                  if ($file!=='.'&&$file!=='..'&&is_file($folderPath . '/' . $file)) {
                    $lstAtt[$file]=$folderPath . $file;
                    if (file_exists($folderPath . $file) and $lstAtt[$file]!='') {
                      $addAttachToMessage.="<td colspan='2' style='background:#ffffff;text-align:left;width:70%;padding-left:20px;padding-bottom:10px;vertical-align:top;padding-bottom:10px;'><div>" . $file . "</div></td></tr>";
                    } else {
                      $addAttachToMessage.="<td colspan='2' ><div style='background:#ffffff;text-align:left;width:70%;padding-left:20px;padding-bottom:10px;vertical-align:top;padding-bottom:10px;color:red;'>" . $file . $notFound . "</div></td></tr>";
                    }
                  }
                }
              } else {
                $att=new Attachment($val[0]);
                $lstAtt[$att->fileName]=pq_str_replace('${attachmentDirectory}', $directory, $att->subDirectory) . $att->fileName;
                if (file_exists(pq_str_replace('${attachmentDirectory}', $directory, $att->subDirectory) . $att->fileName) and $lstAtt[$att->fileName]!='') {
                  $addAttachToMessage.="<td colspan='2' style='background:#ffffff;text-align:left;width:70%;padding-left:20px;padding-bottom:10px;vertical-align:top;padding-bottom:10px;'><div>" . $att->fileName . "</div></td></tr>";
                } else {
                  $addAttachToMessage.="<td colspan='2' ><div style='background:#ffffff;text-align:left;width:70%;padding-left:20px;padding-bottom:10px;vertical-align:top;padding-bottom:10px;color:red;'>" . $att->fileName . $notFound . "</div></td></tr>";
                }
              }
            } else if ((int)$val[0]) {
              $doc=new DocumentVersion($val[0]);
              $lstAtt[$doc->fileName]=$doc->getUploadFileName();
              if (file_exists($doc->getUploadFileName()) and $lstAtt[$doc->fileName]!='') {
                $addAttachToMessage.="<td colspan='2' ><div style='background:#FFFFFF;text-align: left;'>" . $doc->fileName . "</div></td></tr>";
              } else {
                $addAttachToMessage.="<td colspan='2' ><div style='background:#FFFFFF;text-align: left;color:red;'>" . $doc->fileName . $notFound . "</div></td></tr>";
              }
            }
          }
          $addAttachToMessage.="</table>";
          $attachments=$lstAtt;
        }
        //
        if ($emailTemplateTab[$j]->name=='basic') {
          $emailTemplateTab[$j]->template=$this->getMailDetail();
          if ($directStatusMail and isset($directStatusMail->message)) {
            // florent
            $emailTemplateTab[$j]->template=$this->getMailDetail($directStatusMail->message);
          }
          $emailTemplateTab[$j]->title=$title;
          $emailTemplateTab[$j]->template='<html><head><title>' . $title . '</title></head><body style="font-family: Verdana, Arial, Helvetica, sans-serif;">' . $emailTemplateTab[$j]->template . $addAttachToMessage . '</body></html>';
        } else {
          // florent #4442
          $tempAttach='Yes';
          $maxSizeAttachment=Parameter::getGlobalParameter('paramAttachmentMaxSizeMail');
          if ($maxSizeAttachment=='') {
            $maxSizeAttachment=0;
          }
          if (pq_strpos($emailTemplateTab[$j]->template, '${lastAttachment}')!==false) {
            $attachments=array();
            $valueAttach=pq_explode('/', $this->searchLastAttachmentMailable());
            if ($valueAttach[0]!='') {
              $fileSize=$valueAttach[1];
              if ($fileSize<$maxSizeAttachment) {
                $attachments[]=pq_explode('_', $valueAttach[0]);
                foreach ($attachments as $val) {
                  $att=new Attachment($val[0]);
                  $lstAtt[$att->fileName]=pq_str_replace('${attachmentDirectory}', $directory, $att->subDirectory) . $att->fileName;
                  $attachments=$lstAtt;
                }
              } else {
                return array('result'=>'ErrorSize', 'dest'=>"");
              }
            }
          } else if (pq_strpos($emailTemplateTab[$j]->template, '${allAttachments}')!==false) {
            $res=$this->searchAllAttachmentsMailable($maxSizeAttachment);
            $attachments=$res['attachments'];
            $erroSize=($res['result']!='Ok')?i18n('toLargeAllNotAttached'):'';
            if (!empty($attachments)) {
              foreach ($attachments as $val) {
                $att=new Attachment($val[0]);
                $lstAtt[$att->fileName]=pq_str_replace('${attachmentDirectory}', $directory, $att->subDirectory) . $att->fileName;
              }
              $attachments=$lstAtt;
            } else {
              $erroSize='';
            }
          }
          //
          $emailTemplateTab[$j]->template=$this->getMailDetailFromTemplate($emailTemplateTab[$j]->template);
          if ($emailTemplateTab[$j]->title=='' or $emailTemplateTab[$j]->title==null) {
            $emailTemplateTab[$j]->title=$title;
          } else {
            $emailTemplateTab[$j]->title=$this->getMailDetailFromTemplate($emailTemplateTab[$j]->title, null, true);
          }
        }
        if (pq_trim(pq_str_replace(array(',', ';', ' '), '', $destTab[$emailTemplateTab[$j]->id]))) {
          $toSendNowArray=array();
          $to=pq_str_replace(" ", "", $destTab[$emailTemplateTab[$j]->id]);
          $userList=pq_explode(",", $to);
          $title=$emailTemplateTab[$j]->title;

          foreach ($userList as $user) {
            // Checking if the mail has already been sent to the user
            if (!pq_array_key_exists($user, $sentArray)||!pq_array_key_exists($title, $sentArray[$user])||!pq_array_key_exists($emailTemplateTab[$j]->id, $sentArray[$user][$title])) {
              if (!pq_array_key_exists($user, $sentArray)) {
                $sentArray[$user]=array();
              }
              if (!pq_array_key_exists($title, $sentArray[$user])) {
                $sentArray[$user][$title]=array();
              }
              if (!pq_array_key_exists($emailTemplateTab[$j]->id, $sentArray[$user][$title])) {
                $sentArray[$user][$title][$emailTemplateTab[$j]->id]=array();
              }
              $toSendNowArray[$user]=$user;
            }
          }
          // Group every user to only send one email
          $userString=implode(',', $toSendNowArray);
          if ($userString) {
            $resultMail[]=sendMail($userString, $title, $emailTemplateTab[$j]->template, $this, null, $sender, null, null, $references, false, false, $attachments, $erroSize, $tempAttach);
          }
        }
      }
    }
    // END add gmartin
    if ($directStatusMail) {
      $idTemplate=(pq_trim($directStatusMail->idEmailTemplate))?$directStatusMail->idEmailTemplate:'0';
      if (Parameter::getUserParameter('notReceiveHisOwnEmails')=='YES' and !$cronnedScript) {
        $tabDest=pq_explode(",", $destTab[$idTemplate]);
        if (count($tabDest)!=count($resultMail)) {
          $curUser=new Affectable(getSessionUser()->id, true);
          foreach ($tabDest as $id=>$mail) {
            if (pq_trim($mail)==$curUser->email) {
              unset($tabDest[$id]);
            }
          }
        }
        $destTab[$idTemplate]=implode(",", $tabDest);
      }
      if ($resultMail and $resultMail[0]!='') {
        return array('result'=>'OK', 'dest'=>$destTab[$idTemplate]);
      } else if ($resultMail[0]=='' and Parameter::getUserParameter('notReceiveHisOwnEmails')=='YES' and pq_trim(Parameter::getUserParameter('paramMailSmtpServer'))!='') {
        return array('result'=>'Fail', 'dest'=>$destTab[$idTemplate]);
      } else {
        return array('result'=>'', 'dest'=>$destTab[$idTemplate]);
      }
    }

    $valide=0;
    if ($resultMail and is_array($resultMail)) {
      foreach ($resultMail as $id=>$value) {
        if ($value!='') {
          $valide++;
        }
      }
    }
    if ($valide!=0) {
      return $resultMail;
    }
    return;
  }

  public function sendAlertNotification($newItem=false, $statusChange=false, $directStatusMail=null, $responsibleChange=false, $noteAdd=false, $attachmentAdd=false, $noteChange=false, $descriptionChange=false, $resultChange=false, $assignmentAdd=false, $assignmentChange=false, $anyChange=false, $affectationAdd=false, $affectationChange=false, $linkAdd=false, $linkDelete=false, $attachments=false, $priorityChange=false, $newUserCreated=false) {
    global $cronnedScript, $doNotTriggerAlerts;
    if ($doNotTriggerAlerts==true) return false;
    $objectClass=get_class($this);
    $idProject=($objectClass=='Project')?$this->id:((property_exists($this, 'idProject'))?$this->idProject:null);
    if ($objectClass=='TicketSimple') {
      $objectClass='Ticket';
    }
    if (($objectClass=='Resource' or $objectClass=='Contact') and $newUserCreated) $objectClass='User';
    if ($objectClass=='History' or $objectClass=='Audit' or $objectClass=='KpiHistory' or !in_array($objectClass, SqlList::getListNotTranslated('Mailable'))) {
      return false; // exit : not for History
    }
    $statusMailList=array();
    $statusMailListOrganized=array();
    $statusMail=new StatusMail();
    if ($objectClass=='Affectation') {
      $mailable=SqlElement::getSingleSqlElementFromCriteria('Mailable', array('name'=>'Project'));
    } else {
      $mailable=SqlElement::getSingleSqlElementFromCriteria('Mailable', array('name'=>$objectClass));
    }
    if (!$mailable or !$mailable->id) {
      return false; // exit if not mailable object
    }
    $crit="idle=0";
    $crit.=" and idMailable=" . $mailable->id . " and ( 1=0 ";
    if ($statusChange and property_exists($this, 'idStatus') and pq_trim($this->idStatus)) {
      $any=SqlElement::getSingleSqlElementFromCriteria('EventForMail', array('name'=>'statusChange'));
      $crit.="  or idStatus=" . $this->idStatus . " or idEventForMail=" . $any->id . " ";
    }
    if ($responsibleChange) {
      $crit.=" or idEventForMail=1 ";
    }
    if ($noteAdd) {
      $crit.=" or idEventForMail=2 ";
    }
    if ($attachmentAdd) {
      $crit.=" or idEventForMail=3 ";
    }
    if ($noteChange) {
      $crit.=" or idEventForMail=4 ";
    }
    if ($descriptionChange) {
      $crit.=" or idEventForMail=5 ";
    }
    if ($resultChange) {
      $crit.=" or idEventForMail=6 ";
    }
    if ($assignmentAdd) {
      $crit.=" or idEventForMail=7 ";
    }
    if ($assignmentChange) {
      $crit.=" or idEventForMail=8 ";
    }
    if ($anyChange) {
      $crit.=" or idEventForMail=9 ";
    }
    if ($affectationAdd) {
      $crit.=" or idEventForMail=10 ";
    }
    if ($affectationChange) {
      $crit.=" or idEventForMail=11 ";
    }
    if ($linkAdd) {
      $crit.=" or idEventForMail=12 ";
    }
    if ($linkDelete) {
      $crit.=" or idEventForMail=13 ";
    }
    if ($statusChange) {
      $crit.=" or idEventForMail=14 ";
    }
    if ($priorityChange) {
      $crit.=" or idEventForMail=15 ";
    }
    if ($newUserCreated) {
      $crit.=" or idEventForMail=16 ";
    }
    $crit.=")";

    $statusMailList=$statusMail->getSqlElementsFromCriteria(null, false, $crit);
    // $typeName='id'.$objectClass.'Type';
    $typeName=SqlElement::getTypeName($objectClass);
    $proj=null;
    $type=null;
    if (property_exists($this, "idProject")) {
      $proj=($objectClass=='Project')?$this->id:$this->idProject;
      $project=new Project($proj, true);
      $topList=$project->getTopProjectList(true);
    }
    if (property_exists($this, $typeName)) {
      $type=$this->$typeName;
    }
    $isSubProj=false;
    foreach ($statusMailList as $stm) {
      $isSubProj=false;
      if ($proj and $stm->idProject) {
        if (in_array($stm->idProject, $topList)) {
          // $statusMailListOrganized[$stm->idEventForMail]=$stm;
          $isSubProj=true;
        }
      }
      if ($proj and $stm->idProject and $stm->idProject!=$proj and !$isSubProj) { // Does not concern current project, must not apply
        continue;
      }
      if ($type and $stm->idType and $stm->idType!=$type) { // Does not concern current type, must not apply
        continue;
      }
      if (!$stm->idEventForMail) $stm->idEventForMail=0;
      if (!isset($statusMailListOrganized[$stm->idEventForMail])) { // No other already selected : OK
        $statusMailListOrganized[$stm->idEventForMail]=$stm;
        continue;
      }
      // Now we are treating duplicates (already exists for event, we have another one that may fit, so we must select on Project and / or Type
      if ($proj and $stm->idProject and ($stm->idProject==$proj or $isSubProj)) { // OK, dedicated to correct project (or top one)
        if (!$statusMailListOrganized[$stm->idEventForMail]->idProject) {
          $statusMailListOrganized[$stm->idEventForMail]=$stm; // Found rule on projet, previous was not
        } else if (array_search($stm->idProject, $topList)<array_search($statusMailListOrganized[$stm->idEventForMail]->idProject, $topList)) {
          $statusMailListOrganized[$stm->idEventForMail]=$stm; // Found rule with projet "neared" on parents list than previously stored
        } else if ($stm->idProject and array_search($stm->idProject, $topList)>array_search($statusMailListOrganized[$stm->idEventForMail]->idProject, $topList)) {
          continue; // Found rule with projet "farther" on parents list than previously stored
        } else if ($type and $stm->idType and $stm->idType==$type) {
          $statusMailListOrganized[$stm->idEventForMail]=$stm; // Same project than previously stored and type match : this is this one !!!!
        } else {
          continue; // Same project than previously stored and not type match : pass ! (duplicate ?)
        }
      } else { // Not project defined rule, will check on type
        if ($type and $stm->idType and $stm->idType==$type) { // Same type but not same project, replace if previous not on project
          if (!isset($statusMailListOrganized[$stm->idEventForMail]) or !$statusMailListOrganized[$stm->idEventForMail]->idProject) {
            $statusMailListOrganized[$stm->idEventForMail]=$stm; // Same type and previously stored not on project neither : store
          } else {
            continue; // Not same Same project than previously stored and not type match : pass ! (duplicate ?)
          }
        }
      }
    }

    $destTab=array(); // store the mail adressses and the templates names that will be used to send the mails. replace : $dest
    $emailTemplateTab=array();
    $i=0;
    foreach ($statusMailListOrganized as $statusMail) {
      $emailTemplateTab[$i]=new EmailTemplate($statusMail->idEmailTemplate);
      if ($emailTemplateTab[$i]->name==null) {
        $emailTemplateTab[$i]->name='basic';
        $emailTemplateTab[$i]->id='0';
      }
      $destTab[$emailTemplateTab[$i]->id]=null;

      if ($statusMail->idType) {
        if (property_exists($this, 'idType') and $this->idType!=$statusMail->idType) {
          continue; // exist : not corresponding type
        }
        // $typeName = 'id' . $objectClass . 'Type';
        $typeName=SqlElement::getTypeName($objectClass);
        if (property_exists($this, $typeName) and $this->$typeName!=$statusMail->idType) {
          continue; // exist : not corresponding type
        }
      }
      // if ($statusMail->mailToUser == 0 and $statusMail->mailToAccountable == 0 and $statusMail->mailToResource == 0 and $statusMail->mailToProject == 0 and $statusMail->mailToLeader == 0 and $statusMail->mailToContact == 0 and $statusMail->mailToOther == 0 and $statusMail->mailToManager == 0 and $statusMail->mailToAssigned == 0 and $statusMail->mailToSubscribers == 0 and $statusMail->mailToSponsor == 0 and $statusMail->mailToProjectIncludingParentProject == 0 and $statusMail->mailToFinancialResponsible == 0) {
      // continue; // exit not a status for mail sending (or disabled)
      // }

      if ($statusMail->alertToAssigned) {
        $ass=new Assignment();
        $crit=array('refType'=>$objectClass, 'refId'=>$this->id);
        $assList=$ass->getSqlElementsFromCriteria($crit);
        foreach ($assList as $ass) {
          $res=new ResourceAll($ass->idResource, true);
          $newDest="###" . $res->id . "###";
          if (!$res->idle and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }

      if ($statusMail->alertToAccountable) {
        if (property_exists($this, 'idAccountable')) {
          $resource=new Resource($this->idAccountable, true);
          $newDest="###" . $resource->id . "###";
          if (!$resource->idle and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }

      if ($statusMail->alertToUser) {
        if (property_exists($this, 'idUser')) {
          $user=new User($this->idUser, true);
          $newDest="###" . $user->id . "###";
          if (!$user->idle and $user->id and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->alertToResource) {
        if (property_exists($this, 'idResource')) {
          $resource=new Resource($this->idResource, true);
          $newDest="###" . $resource->id . "###";
          if (!$resource->idle and $resource->id and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }
      if ($statusMail->alertToProject or $statusMail->alertToLeader or $statusMail->alertToProjectIncludingParentProject) {
        $aff=new Affectation();
        if ($statusMail->alertToProjectIncludingParentProject) {
          $proj=new Project($idProject, true);
          $critWhere="idle=0 and idProject in " . transformValueListIntoInClause($proj->getTopProjectList(true));
          $affList=$aff->getSqlElementsFromCriteria(null, false, $critWhere);
        } else {
          $crit=array('idProject'=>$idProject, 'idle'=>'0');
          $affList=$aff->getSqlElementsFromCriteria($crit, false);
        }
        if ($affList and count($affList)>0) {
          foreach ($affList as $aff) {
            $resource=new Affectable($aff->idResource, true);
            if ($statusMail->alertToProject or $statusMail->alertToProjectIncludingParentProject) {
              if ($aff->idResource==getSessionUser()->id) {
                $usr=getSessionUser();
              } else {
                $usr=new User($aff->idResource, true);
              }
              if (!$resource->idle) {
                $newDest="###" . $resource->id . "###";
                if ($resource->id and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
                  $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
                  $destTab[$emailTemplateTab[$i]->id].=$newDest;
                }
              }
            }
            if ($statusMail->alertToLeader and ($aff->idProfile or $resource->idProfile)) {
              $profile=($aff->idProfile)?$aff->idProfile:$resource->idProfile;
              $prf=new Profile($profile);
              if ($prf->profileCode=='PL') {
                $newDest="###" . $resource->id . "###";
                if (!$resource->idle and $resource->id and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
                  $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
                  $destTab[$emailTemplateTab[$i]->id].=$newDest;
                }
              }
            }
          }
        }
      }
      if ($statusMail->alertToManager) {
        if (property_exists($this, 'idProject')) {
          $project=new Project($idProject, true);
          $manager=new Affectable($project->idResource, true);
          $newDest="###" . $manager->id . "###";
          if (!$manager->idle and $manager->email and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }

      if ($statusMail->alertToContact) {
        if (property_exists($this, 'idContact')) {
          $contact=new Affectable($this->idContact, true);
          if ($contact->isUser) {
            $newDest="###" . $contact->id . "###";
            if (!$contact->idle and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
              $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
              $destTab[$emailTemplateTab[$i]->id].=$newDest;
            }
          }
        }
      }
      if ($statusMail->alertToSubscribers) {
        $crit="(refType='" . $objectClass . "' and refId=" . Sql::fmtId($this->id) . ")";
        if (property_exists($this, 'idProject')) {
          $crit.=" or (refType='Project' and refId=" . Sql::fmtId($this->idProject) . ")";
        }
        $sub=new Subscription();
        $lstSub=$sub->getSqlElementsFromCriteria(null, null, $crit);
        foreach ($lstSub as $sub) {
          $resource=new Affectable($sub->idAffectable, true);
          $newDest="###" . $resource->id . "###";
          if (!$resource->idle and $resource->id and pq_strpos($destTab[$emailTemplateTab[$i]->id], $newDest)===false) {
            $destTab[$emailTemplateTab[$i]->id].=($destTab[$emailTemplateTab[$i]->id])?', ':'';
            $destTab[$emailTemplateTab[$i]->id].=$newDest;
          }
        }
      }

      $i++;
    }

    $j=$i;
    while ($i--) {
      if ($destTab[$emailTemplateTab[$i]->id]=='' or $destTab[$emailTemplateTab[$i]->id]==null or pq_str_replace(array(',', ';', ' '), '', $destTab[$emailTemplateTab[$i]->id])=='') {} else {
        $destTab[$emailTemplateTab[$i]->id]=pq_str_replace('###', '', $destTab[$emailTemplateTab[$i]->id]);
      }
    }

    if ($newUserCreated) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNewUserCreated');
    } else if ($newItem) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNew');
    } else if ($noteAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNote');
    } else if ($noteChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleNoteChange');
    } else if ($assignmentAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAssignment');
    } else if ($assignmentChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAssignmentChange');
    } else if ($attachmentAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAttachment');
    } else if ($statusChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleStatus');
    } else if ($responsibleChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleResponsible');
    } else if ($priorityChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitlePriorityChanged');
    } else if ($descriptionChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleDescription');
    } else if ($resultChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleResult');
    } else if ($directStatusMail) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleDirect');
    } else if ($anyChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAnyChange');
    } else if ($affectationAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAffectationAdd');
    } else if ($affectationChange) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleAffectationChange');
    } else if ($linkAdd) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleLinkAdd');
    } else if ($linkDelete) {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitleLinkDelete');
    } else {
      $paramMailTitle=Parameter::getGlobalParameter('paramMailTitle'); // default
    }
    $title=$objectClass . ' #' . $this->id;
    $references=$objectClass . "-" . $this->id;
    $message=$this->parseMailMessage($paramMailTitle);
    $tabDest=array();
    $newTab=array();
    foreach ($destTab as $id=>$value) {
      $tabDest[$id]=pq_explode(",", pq_nvl($value));
    }
    foreach ($tabDest as $tabDest2) {
      foreach ($tabDest2 as $val) {
        $newTab[]=$val;
      }
    }
    // create Alert
    foreach ($newTab as $id=>$value) {
      if (!$value) continue;
      $alert=new Alert();
      if (get_class($this)=='Project') {
        $alert->idProject=$this->id;
      } else {
        $alert->idProject=$this->idProject;
      }
      $alert->refType=get_class($this);
      $alert->refId=$this->id;
      $alert->idUser=$value;
      $alert->alertType='INFO';
      $messages=new Html2Text($message);
      $message=$messages->get_text();
      $alert->message=$message;
      $alert->title=$title;
      $alert->readFlag=0;
      $alert->alertInitialDateTime=date('Y-m-d H:i:s');
      $alert->alertDateTime=date('Y-m-d H:i');
      $alert->idle=0;
      $alert->save();
    }
    return;
  }

  public static function getBaseUrl() {
    if (isset($_SERVER['REQUEST_URI'])) {
      $uri=$_SERVER['REQUEST_URI'];
    } else { // FIX FOR IIS
      if (isset($_SERVER['PHP_SELF'])) {
        $uri=pq_substr($_SERVER['PHP_SELF'], 1);
        if (isset($_SERVER['QUERY_STRING'])) {
          $uri.='?' . $_SERVER['QUERY_STRING'];
        }
      } else {
        $uri='/view/main.php';
      }
    }
    $port=(isset($_SERVER['SERVER_PORT']))?$_SERVER['SERVER_PORT']:'80';
    $https=(isset($_SERVER)&&isset($_SERVER['HTTPS']))?$_SERVER['HTTPS']:'off';
    // $https=(isset($_SERVER) || (isset($_SERVER) && $_SERVER === 'https'))?'on':'off'; // Proposal from vanrar68
    if (Parameter::getGlobalParameter('paramHttps')!='') $https=Parameter::getGlobalParameter('paramHttps');
    $serverName=(isset($_SERVER['SERVER_NAME']))?$_SERVER['SERVER_NAME']:'';
    if ((!$serverName or pq_strlen($serverName)<=3) and isset($_SERVER['SERVER_ADDR'])) $serverName=$_SERVER['SERVER_ADDR'];
    $url=(($https and pq_strtolower($https)=='on') or $port=='443')?'https://':'http://';
    $url.=$serverName;
    $url.=($port!='80' and $port!='443')?':' . $port:'';
    $url.=$uri;
    $ref="";
    if (pq_strpos($url, '/view/')) { // Attention, to give correct url for csv export, view must be first
      $ref.=pq_substr($url, 0, pq_strpos($url, '/view/'));
    } else if (pq_strpos($url, '/tool/')) {
      $ref.=pq_substr($url, 0, pq_strpos($url, '/tool/'));
    } else if (pq_strpos($url, '/report/')) {
      $ref.=pq_substr($url, 0, pq_strpos($url, '/report/'));
    } else if (pq_strpos($url, '/sso/projeqtor/')) {
      $ref.=pq_substr($url, 0, pq_strpos($url, '/sso/projeqtor/'));
    } else if (pq_strpos($url, '/sso/')) {
      $ref.=pq_substr($url, 0, pq_strpos($url, '/sso/'));
    } else if (pq_strpos($url, '/mobile/')) {
      $ref.=pq_substr($url, 0, pq_strpos($url, '/mobile/'));
    } else if (pq_strpos($url, '/plugin')) {
      $ref.=pq_substr($url, 0, pq_strpos($url, '/plugin/'));
    }
    return $ref;
  }

  public function parseMailMessage($message) {
    $arrayFrom=array();
    $arrayTo=array();
    $objectClass=get_class($this);
    if ($objectClass=='TicketSimple') {
      $objectClass='Ticket';
    }
    $item=i18n($objectClass);
    if ($objectClass=='Project') {
      $project=$this;
    } else if (property_exists($this, 'idProject')) {
      $project=new Project($this->idProject, true);
    } else {
      $project=new Project();
    }

    // db display name
    $arrayFrom[]='${dbName}';
    $arrayTo[]=Parameter::getGlobalParameter('paramDbDisplayName');

    // Class of item
    $arrayFrom[]='${item}';
    $arrayTo[]=$item;

    // id
    $arrayFrom[]='${id}';
    $arrayTo[]=$this->id;

    // name
    $arrayFrom[]='${name}';
    $arrayTo[]=(property_exists($this, 'name'))?$this->name:'';

    // status
    $arrayFrom[]='${status}';
    $arrayTo[]=(property_exists($this, 'idStatus'))?SqlList::getNameFromId('Status', $this->idStatus):'';

    // project
    $arrayFrom[]='${project}';
    $arrayTo[]=$project->name;

    // type
    // $typeName = 'id' . $objectClass . 'Type';
    $typeName=SqlElement::getTypeName($objectClass);
    $arrayFrom[]='${type}';
    $arrayTo[]=(property_exists($this, $typeName))?SqlList::getNameFromId(SqlElement::getTypeClassName($objectClass), $this->$typeName):'';

    // reference
    $arrayFrom[]='${reference}';
    $arrayTo[]=(property_exists($this, 'reference'))?$this->reference:'';

    // externalReference
    $arrayFrom[]='${externalReference}';
    $arrayTo[]=(property_exists($this, 'externalReference'))?$this->externalReference:'';

    // issuer
    $arrayFrom[]='${issuer}';
    $arrayTo[]=(property_exists($this, 'idUser'))?SqlList::getNameFromId('Affectable', $this->idUser):'';

    // responsible
    $arrayFrom[]='${responsible}';
    $arrayTo[]=(property_exists($this, 'idResource'))?SqlList::getNameFromId('Resource', $this->idResource):'';

    // sender
    $arrayFrom[]='${sender}';
    $user=getSessionUser();
    $arrayTo[]=($user->resourceName)?$user->resourceName:$user->name;

    // context1 to context3
    $arrayFrom[]='${context1}';
    $arrayFrom[]='${context2}';
    $arrayFrom[]='${context3}';
    $arrayTo[]=(property_exists($this, 'idContext1'))?SqlList::getNameFromId('Context', $this->idContext1):'';
    $arrayTo[]=(property_exists($this, 'idContext2'))?SqlList::getNameFromId('Context', $this->idContext2):'';
    $arrayTo[]=(property_exists($this, 'idContext3'))?SqlList::getNameFromId('Context', $this->idContext3):'';

    // sponsor
    $arrayFrom[]='${sponsor}';
    $arrayTo[]=SqlList::getNameFromId('Sponsor', $project->idSponsor);

    // projectCode
    $arrayFrom[]='${projectCode}';
    $arrayTo[]=$project->projectCode;

    // ContractCode
    $arrayFrom[]='${contractCode}';
    $arrayTo[]=$project->contractCode;

    // Customer
    $arrayFrom[]='${customer}';
    $arrayTo[]=SqlList::getNameFromId('Client', $project->idClient);

    // url (direct access to item)
    $arrayFrom[]='${url}';
    if ($objectClass=='User') {
      // FIX FOR IIS
      $arrayTo[]=self::getBaseUrl();
    } else {
      $arrayTo[]=$this->getReferenceUrl();
    }

    // login
    $arrayFrom[]='${login}';
    $arrayTo[]=($objectClass=='User')?$this->name:getSessionUser()->name;

    // password
    $arrayFrom[]='${password}';
    $arrayTo[]=($objectClass=='User')?(($this->crypto===null)?$this->password:'(' . i18n("passwordAlreadyChanged") . ')'):'';

    // admin mail
    $arrayFrom[]='${adminMail}';
    $arrayTo[]=Parameter::getGlobalParameter('paramAdminMail');

    // Format title
    return pq_str_replace($arrayFrom, $arrayTo, $message);
  }

  /**
   * Get the detail of object, to be send by mail
   * This is a simplified copy of objectDetail.php, in print mode
   */
  public function getMailDetail($directMessage=null) {
    $currencyPosition=Parameter::getGlobalParameter('currencyPosition');
    $currency=Parameter::getGlobalParameter('currency');
    SqlList::cleanAllLists(); // To be sure...
    $msg="";
    $rowStart='<tr>';
    $rowEnd='</tr>';
    $labelStart='<td style="background:#FFFFFF;font-weight:bold;text-align: right;width:30%;min-width:30%;vertical-align: middle;white-space:nowrap;padding-bottom:10px;">&nbsp;&nbsp;';
    $labelLinkStart='<td style="background:#FFFFFF;text-align: right;width:30%;min-width:30%;vertical-align: top;white-space:nowrap;padding-bottom:10px;">&nbsp;&nbsp;';
    $labelEnd='&nbsp;</td>';
    $fieldStart='<td style="background:#FFFFFF;text-align: left;width:70%;padding-left:20px;padding-bottom:10px;vertical-align: top;">'; // <td style="width:2px;">&nbsp;</td>
    $fieldEnd='</td>';
    $sectionStart='<td style="background:#606062;color: #FFFFFF; text-align: center;font-size:14pt;font-weight:normal;width: 100%;font-family:Verdana,Arial,Helvetica,sans-serif" colspan="2">';
    $sectionEnd='</td>';
    $tableStart='<table style="font-size:11pt; width: 100%;font-family: Verdana, Arial, Helvetica, sans-serif;">';
    $tableEnd='</table>';
    // florent
    $ref=$this->getReferenceUrl();
    $replyMail=i18n("replyToMail");
    $firstLine=" 
        <table style='font-size:14pt;min-width: 800px; max-width: 1200px; width:95%;font-family:Verdana,Arial,Helvetica,sans-serif;padding-bottom:10px;'><tr style='height:22px;'>
        <td colspan='2' style='background:#606062;color: #FFFFFF; text-align: center;vertical-align: middle;'>
        <div style='background:#F0F0F0;color:#A0A0A0;font-style:italic;font-size:80%'>" . htmlEncode($replyMail) . "</div><div style='background:#606062;color:#606062;font-size:1pt;'>###PROJEQTOR###</div>
        <div style='vertical-align: middle;'>
        <img style='width:22px; height:22px;-webkit-filter :brightness(0) invert(1);filter: brightness(0) invert(1);' src='" . self::getBaseUrl() . "/view/css/customIcons/grey/icon" . get_class($this) . ".png'/>
        &nbsp;
        <a href='" . $ref . "' target='#' style='color:white'>" . i18n(get_class($this)) . " #" . htmlEncode($this->id) . "</a></div></td>
        </tr>";
    $dmsg=(isset($directMessage))?$this->parseMailMessage($directMessage):'';
    $inputmailboxTicket=new InputMailboxTicket();
    $countInputMailBox=$inputmailboxTicket->countSqlElementsFromCriteria(array('idle'=>'0'));
    if ((Parameter::getGlobalParameter('cronCheckEmailsHost')!='' and Parameter::getGlobalParameter('cronCheckEmails')>0) or $countInputMailBox>0) {
      $msg=" \n " . $firstLine . " \n <tr><td colspan='2'>" . $dmsg . "</td></tr>\n";
    } else {
      $msg="<table style='font-size:14pt;min-width: 800px; max-width: 1200px; width:95%;font-family:Verdana,Arial,Helvetica,sans-serif;'><tr style='height:22px;'>";
      $msg.="  <td colspan='2' style='background:#606062;color: #FFFFFF; text-align: center;vertical-align: middle;'><div style='vertical-align: middle;'>";
      $msg.="  <img style='width:22px; height:22px;-webkit-filter :brightness(0) invert(1);filter: brightness(0) invert(1);' src='" . self::getBaseUrl() . "/view/css/customIcons/grey/icon" . get_class($this) . ".png'/>";
      $msg.='  &nbsp;';
      $msg.="  <a href='" . $ref . "' target='#' style='color:white'>" . i18n(get_class($this)) . " #" . htmlEncode($this->id) . "</a></div></td>";
      $msg.="  </tr>";
      $msg.=" \n <tr><td colspan='2'>" . $dmsg . "</td></tr>\n";
    }
    $msg.='<tr><td style="padding-bottom:10px" colspan="2"></td></tr>';
    $msg.='<tr>';
    $msg.=' <td style="text-align:center;font-size:14pt;color:#606062;background:#DDDDDD;border:1px solid #606062;vertical-align: middle;" colspan="2">' . SqlList::getNameFromId(get_class($this), $this->id) . '</td>';
    $msg.='</tr>';
    $msg.='<tr><td style="padding-bottom:10px" colspan="2"></td></tr>';
    //
    $colArray=array();
    $section=null;
    $nobr=false;
    foreach ($this as $col=>$val) {
      $hide=false;
      $nobr_before=$nobr;
      $nobr=false;
      if (pq_substr($col, 0, 4)=='_tab') {
        // Nothing
      } else if (pq_substr($col, 0, 5)=='_sec_') {
        if (pq_strlen($col)>8) {
          $section=pq_substr($col, 5);
          $section=pq_ucfirst($section);
          if ($section=='Description' or $section=='Treatment') {
            $colArray[$section]=array($col=>$section);
          }
        } else {
          $section='';
        }
      } else if (pq_substr($col, 0, 5)=='_spe_') {
        // Nothing
      } else if (pq_substr($col, 0, 6)=='_calc_') {
        $item=pq_substr($col, 6);
        $colArray[$section][$col]=$item;
      } else if (pq_substr($col, 0, 5)=='_lib_') {
        $item=pq_substr($col, 5);
        if (pq_strpos($this->getFieldAttributes($col), 'nobr')!==false) {
          $nobr=true;
        }
        $colArray[$section][$col]=$item;
      } else if (pq_substr($col, 0, 5)=='_Link') {
        // Nothing
      } else if (pq_substr($col, 0, 11)=='_Assignment') {
        // Nothing
      } else if (pq_substr($col, 0, 11)=='_Approver') {
        // Nothing
      } else if (pq_substr($col, 0, 15)=='_VersionProject') {
        // Nothing
      } else if (pq_substr($col, 0, 11)=='_Dependency') {
        // Nothing
      } else if ($col=='_ResourceCost') {
        // Nothing
      } else if ($col=='_DocumentVersion') {
        // Nothing
      } else if ($col=='_ExpenseDetail') {
        // Nothing
      } else if (pq_substr($col, 0, 12)=='_TestCaseRun') {
        // Nothing
      } else if (pq_substr($col, 0, 1)=='_' and pq_substr($col, 0, 6)!='_void_' and pq_substr($col, 0, 7)!='_label_') {
        // Nothing
      } else {
        $dataType=$this->getDataType($col);
        $dataLength=$this->getDataLength($col);
        if ($dataType=='decimal' and pq_substr($col, -4, 4)=='Work') {
          $hide=true;
        }
        if (pq_strpos($this->getFieldAttributes($col), 'hidden')!==false) {
          $hide=true;
        }
        if (is_object($val)) {
          if (get_class($val)=='Origin') {
            if ($val->originType and $val->originId) {
              $val=i18n($val->originType) . ' #' . htmlEncode($val->originId) . ' : ' . htmlEncode(SqlList::getNameFromId($val->originType, $val->originId));
            } else {
              $val="";
            }
            $dataType='varchar';
            $dataLength=4000;
          } else {
            $hide=true;
          }
        }
        if ($hide) {
          continue;
        }
        if ($section!=null and $col!=null) $colArray[$section][$col]=$val;
      }
    }
    $msg.=$rowStart . '<td style="width:50%;vertical-align:top;padding-right:15px;min-width:500px;">';
    if (isset($colArray['Description'])) self::drawMailDetailCol($colArray['Description'], $msg);
    if (isset($colArray['Treatment'])) self::drawMailDetailCol($colArray['Treatment'], $msg);
    $msg.=$fieldEnd . '<td style="width:50%;vertical-align:top;padding-left:15px;">';
    if (isset($this->_Link) and is_array($this->_Link)) {
      $msg.=$tableStart;
      $msg.=$rowStart . $sectionStart . '<table style="float:left;"><tr>';
      $msg.='<td>&nbsp;</td>';
      $msg.='<td><img style="float:left;width:22px; height:22px;" src="' . SqlElement::getBaseUrl() . '/view/css/customIcons/new/iconEmailLinkedElement.png" /></td>';
      $msg.='<td>&nbsp;</td>';
      $msg.='<td style="color: #FFFFFF;font-size:14pt;font-weight:normal;white-space:nowrap;font-family:Verdana,Arial,Helvetica,sans-serif">' . i18n('sectionLink') . '</td>';
      $msg.='<td style="width:90%;">&nbsp;</td>';
      $msg.='</tr></table>' . $sectionEnd . $rowEnd;
      $msg.=$rowStart . '<td><br></td>' . $rowEnd;
      $links=$this->_Link;
      if (count($links)==0 and $this->id) { //
        $link=new Link();
        $className=get_class($this);
        $where="(ref1Type='$className' and ref1Id=$this->id) or (ref2Type='$className' and ref2Id=$this->id)";
        $links=$link->getSqlElementsFromCriteria(null, null, $where);
      }
      foreach ($links as $link) {
        if ($link->ref1Id==$this->id and $link->ref1Type==get_class($this)) {
          $refLinkType=$link->ref2Type;
          $refLinkId=$link->ref2Id;
        } else if ($link->ref2Id==$this->id and $link->ref2Type==get_class($this)) {
          $refLinkType=$link->ref1Type;
          $refLinkId=$link->ref1Id;
        }
        $creationDate=$link->creationDate;
        $msg.=$rowStart . $labelLinkStart;
        $userId=$link->idUser;
        $userName=SqlList::getNameFromId('Affectable', $userId);
        $msg.='<b>' . $userName . '&nbsp;&nbsp;</b>';
        $msg.='<br>' . htmlFormatDateTime($creationDate, false, false, false);
        $msg.=$labelEnd . $fieldStart;
        $msg.='<b>' . i18n($refLinkType);
        $msg.='&nbsp;#' . $refLinkId . '</b>&nbsp;-&nbsp;';
        $nameLink=SqlList::getNameFromId($refLinkType, $refLinkId);
        $msg.=htmlEncode($nameLink, 'print');
        $msg.=$fieldEnd . $rowEnd;
      }
      $msg.=$tableEnd;
    }
    if (isset($this->_Note) and is_array($this->_Note)) {
      // florent
      $msg.=$tableStart;
      $msg=$this->getNotesClassicTab($msg, $rowStart, $rowEnd, $sectionStart, $sectionEnd, $labelLinkStart, $labelEnd, $fieldStart, $fieldEnd);
      $msg.=$tableEnd;
    }
    $msg.=$fieldEnd . $rowEnd;
    $msg.=$rowStart . '<td style="width:50%;vertical-align:top;">';
    // ADDITION BY papjul - Document Version details
    if (isset($this->_DocumentVersion) and is_array($this->_DocumentVersion)) {
      $msg.=$tableStart;
      $msg.=$rowStart . $sectionStart . '<table style="float:left;"><tr>';
      $msg.='<td>&nbsp;</td>';
      $msg.='<td><img style="width:22px; height:22px;" src="' . SqlElement::getBaseUrl() . '/view/css/customIcons/new/iconEmailAttachment.png" /></td>';
      $msg.='<td>&nbsp;</td>';
      $msg.='<td style="color: #FFFFFF;font-size:14pt;font-weight:normal;white-space:nowrap;font-family:Verdana,Arial,Helvetica,sans-serif">' . i18n('sectionDocumentVersion') . '</td>';
      $msg.='<td style="width:90%;">&nbsp;</td>';
      $msg.='</tr></table>' . $sectionEnd . $rowEnd;
      $documentVersion=new DocumentVersion();
      $documentVersions=$documentVersion->getSqlElementsFromCriteria(array('idDocument'=>$this->id), false, null, 'id desc');
      foreach ($documentVersions as $documentVersion) {
        $name=$documentVersion->name;
        $versionDate=$documentVersion->versionDate;
        $msg.=$rowStart . $labelStart;
        $msg.=$name;
        $msg.='<br />';
        $msg.=htmlFormatDateTime($versionDate, false, false, false);
        $msg.=$labelEnd . $fieldStart;
        $msg.=$documentVersion->fileName;
        $msg.='<br />';
        $text=new Html2Text($documentVersion->description);
        $plainText=$text->getText();
        if (pq_mb_strlen($plainText)>10000 and Parameter::getGlobalParameter('paramAdditionImage')!='YES') { // Should not send too long email
          $descriptionTruncated=nl2br(pq_mb_substr($plainText, 0, 10000));
          $msg.=$descriptionTruncated;
        } else {
          $msg.=$documentVersion->description;
        }
        $msg.=$fieldEnd . $rowEnd;
      }
      $msg.=$tableEnd;
    }
    // End of ADDITION BY papjul - Document Version details
    $msg.=$fieldEnd . $rowEnd . $tableEnd;
    return $msg;
  }

  public function drawMailDetailCol($colArray, &$msg) {
    $currencyPosition=Parameter::getGlobalParameter('currencyPosition');
    $currency=Parameter::getGlobalParameter('currency');
    $rowStart='<tr>';
    $rowEnd='</tr>';
    $labelStart='<td style="background:#FFFFFF;font-weight:bold;text-align: right;width:30%;min-width:30%;vertical-align: top;white-space:nowrap;padding-bottom:10px;">&nbsp;&nbsp;';
    $labelEnd='&nbsp;</td>';
    $fieldStart='<td style="background:#FFFFFF;text-align: left;width:70%;padding-left:20px;padding-bottom:10px;vertical-align: top;">'; // <td style="width:2px;">&nbsp;</td>
    $fieldEnd='</td>';
    $sectionStart='<td style="background:#606062;color: #FFFFFF; text-align: center;font-size:14pt;font-weight:normal;width: 100%;font-family:Verdana,Arial,Helvetica,sans-serif" colspan="2">';
    $sectionEnd='</td>';
    $tableStart='<table style="font-size:11pt; width: 100%;font-family: Verdana, Arial, Helvetica, sans-serif;">';
    $tableEnd='</table>';

    $section=null;
    $nobr=false;
    foreach ($colArray as $col=>$val) {
      $hide=false;
      $nobr_before=$nobr;
      $nobr=false;
      if (pq_substr($col, 0, 4)=='_tab') {
        // Nothing
      } else if (pq_substr($col, 0, 5)=='_sec_') {
        if (pq_strlen($col)>8) {
          $section=pq_substr($col, 5);
          $section=pq_ucfirst($section);
          if ($section=='Description' or $section=='Treatment') {
            $msg.=$tableStart;
            $msg.=$rowStart . $sectionStart . '<table><tr>';
            $msg.='<td>&nbsp;</td>';
            $msg.='<td><img style="float:left;width:22px; height:22px;" src="' . SqlElement::getBaseUrl() . '/view/css/customIcons/new/iconEmail' . $section . '.png" /></td>';
            $msg.='<td>&nbsp;</td>';
            $msg.='<td style="color: #FFFFFF;font-size:14pt;font-weight:normal;white-space:nowrap;font-family:Verdana,Arial,Helvetica,sans-serif">' . i18n('section' . $section) . '</td>';
            $msg.='<td style="width:90%;">&nbsp;</td>';
            $msg.='</tr></table>' . $sectionEnd . $rowEnd;
            $msg.=$rowStart . '<td><br></td>' . $rowEnd;
          }
        } else {
          $section='';
        }
      } else if (pq_substr($col, 0, 5)=='_spe_') {
        // Nothing
      } else if (pq_substr($col, 0, 6)=='_calc_') {
        $item=pq_substr($col, 6);
        $msg.=$this->drawCalculatedItem($item);
      } else if (pq_substr($col, 0, 5)=='_lib_') {
        $item=pq_substr($col, 5);
        if (pq_strpos($this->getFieldAttributes($col), 'nobr')!==false) {
          $nobr=true;
        }
        if ($this->getFieldAttributes($col)!='hidden') {
          $msg.=(($nobr)?'&nbsp;':'') . i18n($item) . '&nbsp;';
        }
        if (!$nobr) {
          $msg.=$fieldEnd . $rowEnd;
        }
      } else if (pq_substr($col, 0, 5)=='_Link') {
        // Nothing
      } else if (pq_substr($col, 0, 11)=='_Assignment') {
        // Nothing
      } else if (pq_substr($col, 0, 11)=='_Approver') {
        // Nothing
      } else if (pq_substr($col, 0, 15)=='_VersionProject') {
        // Nothing
      } else if (pq_substr($col, 0, 11)=='_Dependency') {
        // Nothing
      } else if ($col=='_ResourceCost') {
        // Nothing
      } else if ($col=='_DocumentVersion') {
        // Nothing
      } else if ($col=='_ExpenseDetail') {
        // Nothing
      } else if (pq_substr($col, 0, 12)=='_TestCaseRun') {
        // Nothing
      } else if (pq_substr($col, 0, 1)=='_' and pq_substr($col, 0, 6)!='_void_' and pq_substr($col, 0, 7)!='_label_') {
        // Nothing
      } else {
        $attributes='';
        $isRequired=false;
        $readOnly=false;
        $specificStyle='';
        $dataType=$this->getDataType($col);
        $dataLength=$this->getDataLength($col);
        if ($dataType=='decimal' and pq_substr($col, -4, 4)=='Work') {
          $hide=true;
        }
        if (pq_strpos($this->getFieldAttributes($col), 'hidden')!==false) {
          $hide=true;
        }
        if (pq_strpos($this->getFieldAttributes($col), 'nobr')!==false) {
          $nobr=true;
        }
        if (pq_strpos($this->getFieldAttributes($col), 'invisible')!==false) {
          $specificStyle.=' visibility:hidden';
        }

        if (is_object($val)) {
          if (get_class($val)=='Origin') {
            if ($val->originType and $val->originId) {
              $val=i18n($val->originType) . ' #' . htmlEncode($val->originId) . ' : ' . htmlEncode(SqlList::getNameFromId($val->originType, $val->originId));
            } else {
              $val="";
            }
            $dataType='varchar';
            $dataLength=4000;
          } else {
            $hide=true;
          }
        }
        if ($hide) {
          continue;
        }
        if (!$nobr_before) {
          $msg.=$rowStart . $labelStart . $this->getColCaption($col) . $labelEnd . $fieldStart;
        } else {
          $msg.="&nbsp;&nbsp;&nbsp;";
        }
        if (is_array($val)) {
          // Nothing
        } else if (pq_substr($col, 0, 6)=='_void_') {
          // Nothing
        } else if (pq_substr($col, 0, 7)=='_label_') {
          // $captionName=pq_substr($col,7);
          // $msg.='<label class="label shortlabel">' . i18n('col' . pq_ucfirst($captionName)) . '&nbsp;:&nbsp;</label>';
        } else if ($hide) {
          // Nothing
        } else if ($dataLength>4000) {
          if (pq_mb_strlen($val)>1000000) {
            $text=new Html2Text($val);
            $plainText=$text->getText();
            $msg.=htmlSetClickableImages(nl2br(pq_mb_substr($plainText, 0, 1000000)), 450, true);
          } else {
            $msg.=htmlSetClickableImages($val, 450, true);
          }
        } else if (pq_strpos($this->getFieldAttributes($col), 'displayHtml')!==false) {
          $msg.=$val;
        } else if ($col=='id') { // id
          $msg.='<span style="color:grey;">#</span>' . $val;
        } else if ($col=='password') {
          $msg.="*****"; // nothing
        } else if ($dataType=='date' and $val!=null and $val!='') {
          $msg.=htmlFormatDate($val, false, false);
        } else if ($dataType=='datetime' and $val!=null and $val!='') {
          $msg.=htmlFormatDateTime($val, false, false, false);
        } else if ($dataType=='time' and $val!=null and $val!='') {
          $msg.=htmlFormatTime($val, false);
        } else if ($col=='color' and $dataLength==7) { // color
                                                       // nothing
        } else if ($dataType=='int' and $dataLength==1) { // boolean
          $msg.='<input type="checkbox" disabled="disabled" ';
          if ($val!='0' and !$val==null) {
            $msg.=' checked />';
          } else {
            $msg.=' />';
          }
          // BEGIN - REPLACE BY TABARY - USE isForeignKey GENERIC FUNCTION
        } else if (isForeignKey($col, $this)) { // Idxxx
                                                // } else if (pq_substr ( $col, 0, 2 ) == 'id' and $dataType == 'int' and strlen ( $col ) > 2 and pq_substr ( $col, 2, 1 ) == pq_strtoupper ( pq_substr ( $col, 2, 1 ) )) { // Idxxx
                                                // END - REPLACE BY TABARY - USE isForeignKey GENERIC FUNCTION
                                                // BEGIN - ADD BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
          $col_withoutAlias=foreignKeyWithoutAlias($col);
          $msg.=htmlEncode(SqlList::getNameFromId(pq_substr($col_withoutAlias, 2), $val), 'print');
          // END - ADD BY TABARY - POSSIBILITY TO HAVE X TIMES IDXXXX IN SAME OBJECT
        } else if (pq_substr($col, 0, 2)=='id' and $dataType=='int' and pq_strlen($col)>2 and pq_substr($col, 2, 1)==pq_strtoupper(pq_substr($col, 2, 1))) { // Idxxx
          $msg.=htmlEncode(SqlList::getNameFromId(pq_substr($col, 2), $val), 'print');
        } else if ($dataLength>100) { // Text Area (must reproduce BR, spaces, ...
          $msg.=htmlEncode($val, 'print');
        } else if ($dataType=='decimal' and self::isAmount($col)) {
          if ($currencyPosition=='after') {
            $msg.=htmlEncode($val, 'print') . ' ' . $currency;
          } else {
            $msg.=$currency . ' ' . htmlEncode($val, 'print');
          }
        } else if ($dataType=='decimal' and pq_substr($col, -4, 4)=='Work') {
          // $msg.= Work::displayWork($val) . ' ' . Work::displayShortWorkUnit();
        } else {
          if ($this->isFieldTranslatable($col)) {
            $val=i18n($val);
          }
          if (pq_strpos($this->getFieldAttributes($col), 'html')!==false) {
            $msg.=$val;
          } else {
            $msg.=htmlEncode($val, 'print');
          }
        }
        if (!$nobr) {
          $msg.=$rowEnd;
        }
      }
    }
    $msg.=$tableEnd;
  }

  /**
   * ========================================================================
   * Return the HTML last changes history table of an object.
   * It is a copy of drawHistoryFromObjects();
   *
   * @return string
   */
  public function getLastChangeTabForObject($obj, $lastChangeDate) {
    global $cr, $print, $treatedObjects;
    if ($lastChangeDate=='full') {
      $lastChangeToShow='1970-01-01 00:00:00';
    } else {
      if (!$lastChangeDate) {
        $lastChangeDate=date('Y-m-d H:i:s');
      }
      $lastChangeToShow=date('Y-m-d H:i:s', pq_strtotime($lastChangeDate)-10); // Get last changes (including last 10 seconds, not only last change)
    }
    require_once "../tool/formatter.php";
    if ($obj->id) {
      $inList="(";
      $inList.="('" . get_class($obj) . "', " . Sql::fmtId($obj->id) . ")";
      if (property_exists($obj, 'WorkElement') and $obj->WorkElement->id) {
        $inList.=",('WorkElement', " . $obj->WorkElement->id . ")";
      }
      if (property_exists($obj, 'PlanningElement') and $obj->PlanningElement->id) {
        $inList.=",('PlanningElement', " . $obj->PlanningElement->id . ")";
      }
      $inList.=")";
    } else {
      $inList="( ('x',0) )";
    }
    $showWorkHistory=true;
    $where=' (refType, refId) in ' . $inList;
    $order=' operationDate desc, id asc';
    $hist=new History();
    $historyList=$hist->getSqlElementsFromCriteria(null, false, $where, $order, false, false);
    $style='border-top: 1px solid #7b7b7b ; border-bottom: 1px solid #7b7b7b;
            background-color:#dddddd; padding:4px;';
    $historyTabHtml='<table style="width:95%; border-collapse:collapse; border:1px solid #7b7b7b;">';

    $historyTabHtml.='<tr><td style="' . $style . 'text-align:center;"colspan="6">' . i18n('elementHistory' . (($lastChangeDate=='full')?'':'Last')) . '</td></tr>' . //
    '<tr><td style="' . $style . '" width="10%">' . i18n('colOperation') . '</td>
                      <td style="' . $style . '" width="14%">' . i18n('colColumn') . '</td>
                      <td style="' . $style . '" width="23%">' . i18n('colValueBefore') . '</td>
                      <td style="' . $style . '" width="23%">' . i18n('colValueAfter') . '</td>
                      <td style="' . $style . '" width="15%">' . i18n('colDate') . '</td>
                      <td style="' . $style . '" width="15%">' . i18n('colUser') . '</td>
                      </tr>';
    $stockDate=null;
    $stockUser=null;
    $stockOper=null;
    if (is_array($historyList) and count($historyList)>0 and is_object($historyList[0])) $dateCmp=new DateTime($historyList[0]->operationDate);
    else return $historyTabHtml . '</table>';
    foreach ($historyList as $hist) {
      if ($hist->operationDate<$lastChangeToShow) break;
      if (pq_substr($hist->colName, 0, 24)=='subDirectory|Attachment|' or pq_substr($hist->colName, 0, 18)=='idTeam|Attachment|' or pq_substr($hist->colName, 0, 25)=='subDirectory|Attachement|' or pq_substr($hist->colName, 0, 19)=='idTeam|Attachement|') {
        continue;
      }
      $colName=($hist->colName==null)?'':$hist->colName;
      $split=pq_explode('|', $colName);
      if (count($split)==3) {
        $colName=$split[0];
        $refType=$split[1];
        $refId=$split[2];
        $refObject='';
      } else if (count($split)==4) {
        $refObject=$split[0];
        $colName=$split[1];
        $refType=$split[2];
        $refId=$split[3];
      } else {
        $refType='';
        $refId='';
        $refObject='';
      }
      if ($refType=='Attachement') {
        $refType='Attachment'; // New in V5 : change Class name, must preserve display for history
      }
      $curObj=null;
      $dataType="";
      $dataLength=0;
      $hide=false;
      $oper=i18n('operation' . pq_ucfirst($hist->operation));
      $user=$hist->idUser;
      $user=SqlList::getNameFromId('Affectable', $user);
      $date=htmlFormatDateTime($hist->operationDate, true, false, false);
      $class="NewOperation";
      if ($stockDate==$hist->operationDate and $stockUser==$hist->idUser and $stockOper==$hist->operation) {
        $oper="";
        $user="";
        $date="";
        $class="ContinueOperation";
      }
      if ($colName!='' or $refType!="") {
        if ($refType) {
          if ($refType=="TestCase") {
            $curObj=new TestCaseRun();
          } else {
            $curObj=new $refType();
          }
        } else {
          $curObj=new $hist->refType();
        }
        if ($curObj) {
          if ($refType) {
            $colCaption=i18n($refType) . ' #' . $refId . ' ' . $curObj->getColCaption($colName);
            if ($refObject) {
              $colCaption=i18n($refObject) . ' - ' . $colCaption;
            }
          } else {
            $colCaption=$curObj->getColCaption($colName);
          }
          $dataType=$curObj->getDataType($colName);
          $dataLength=$curObj->getDataLength($colName);
          if (pq_strpos($curObj->getFieldAttributes($colName), 'hidden')!==false) {
            $hide=true;
          }
        }
      } else {
        $colCaption='';
      }
      if (pq_substr($hist->refType, -15)=='PlanningElement' and $hist->operation=='insert') {
        $hide=true;
      }
      if ($hist->isWorkHistory and !$showWorkHistory) {
        $hide=true;
      }
      if (self::isLocal($colName) and !$obj->hasCurrency()) {
        $hide=true;
      }
      if (!$hide) {
        $historyTabHtml.='<tr>';
        $historyTabHtml.='<td class="historyData' . $class . '" style=" padding:4px; width:10%; border: 1px solid #7b7b7b;">' . $oper . '</td>';
        $historyTabHtml.='<td class="historyData" style=" padding:4px; width:14%; border: 1px solid #7b7b7b;">' . $colCaption . '</td>';
        $oldValue=$hist->oldValue;
        $newValue=$hist->newValue;
        if ($dataType=='int' and $dataLength==1) { // boolean
          $oldValue=htmlDisplayCheckbox($oldValue, true);
          $newValue=htmlDisplayCheckbox($newValue, true);
        } else if (pq_substr($colName, 0, 2)=='id' and pq_strlen($colName)>2 and pq_strtoupper(pq_substr($colName, 2, 1))==pq_substr($colName, 2, 1)) {
          if ($oldValue!=null and $oldValue!='') {
            if ($oldValue==0 and $colName=='idStatus') {
              $oldValue='';
            } else {
              $oldValue=SqlList::getNameFromId(pq_substr($colName, 2), $oldValue);
            }
          }
          if ($newValue!=null and $newValue!='') {
            $newValue=SqlList::getNameFromId(pq_substr($colName, 2), $newValue);
          }
        } else if ($colName=="color") {
          $oldValue=htmlDisplayColoredFull("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", $oldValue);
          $newValue=htmlDisplayColoredFull("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", $newValue);
        } else if ($dataType=='date') {
          $oldValue=htmlFormatDate($oldValue, false, false);
          $newValue=htmlFormatDate($newValue, false, false);
        } else if ($dataType=='datetime') {
          $oldValue=htmlFormatDateTime($oldValue, true, false, false);
          $newValue=htmlFormatDateTime($newValue, true, false, false);
        } else if ($dataType=='decimal' and pq_substr($colName, -4, 4)=='Work') {
          $oldValue=Work::displayWork($oldValue) . ' ' . Work::displayShortWorkUnit();
          $newValue=Work::displayWork($newValue) . ' ' . Work::displayShortWorkUnit();
        } else if ($dataType=='decimal' and self::isAmount($colName)) {
          if (self::isLocal($colName)) {
            $oldValue=htmlDisplayLocalCurrency($obj->idProject, null, $oldValue);
            $newValue=htmlDisplayLocalCurrency($obj->idProject, null, $newValue);
          } else {
            $oldValue=htmlDisplayCurrency($oldValue);
            $newValue=htmlDisplayCurrency($newValue);
          }
        } else if (pq_substr($colName, -8, 8)=='Duration') {
          $oldValue=$oldValue . ' ' . i18n('shortDay');
          $newValue=$newValue . ' ' . i18n('shortDay');
        } else if (pq_substr($colName, -8, 8)=='Progress') {
          $oldValue=$oldValue . ' ' . i18n('colPct');
          $newValue=$newValue . ' ' . i18n('colPct');
        } else if ($colName=='password' or $colName=='apiKey') {
          $allstars="**********";
          if ($oldValue) $oldValue=pq_substr($oldValue, 0, 5) . $allstars . pq_substr($oldValue, -5);
          if ($newValue) $newValue=pq_substr($newValue, 0, 5) . $allstars . pq_substr($newValue, -5);
        } else {
          if (!isTextFieldHtmlFormatted($oldValue)) {
            $oldValue=htmlEncode($oldValue, 'print');
            $oldValue=wordwrap($oldValue, 30, '<wbr>', false);
          }
          if (!isTextFieldHtmlFormatted($newValue)) {
            $newValue=htmlEncode($newValue, 'print');
            $newValue=wordwrap($newValue, 30, '<wbr>', false);
          }
        }
        $historyTabHtml.='<td class="historyData' . (($colName=="color")?' colorNameData" style="':'" style="padding:4px;') . ' width:23%; border: 1px solid #7b7b7b;">' . $oldValue . '</td>';
        $historyTabHtml.='<td class="historyData' . (($colName=="color")?' colorNameData" style="':'" style="padding:4px;') . ' width:23%; border: 1px solid #7b7b7b;">' . $newValue . '</td>';
        $historyTabHtml.='<td class="historyData' . $class . '" style="width:15%; border: 1px solid #7b7b7b;">';
        $historyTabHtml.=$date . '</td>';
        $historyTabHtml.='<td class="historyData' . $class . '" style=" padding:4px; width:15%; border-right: 1px solid #AAAAAA;" >';
        if ($user) {
          $historyTabHtml.=formatUserThumb($hist->idUser, $user, null, '16', 'left') . '&nbsp;';
        }
        $historyTabHtml.=$user . '</td>
                          </tr>';
        $stockDate=$hist->operationDate;
        $stockUser=$hist->idUser;
        $stockOper=$hist->operation;
      }
    }
    return $historyTabHtml . '</table>';
  }

  function getAssignmentHtmlTab() {
    $ass=new Assignment();
    $class=get_class($this);
    $id=$this->id;
    $crit=" refType='$class' and refId=$id ";
    $linkAss=$ass->getSqlElementsFromCriteria(null, null, $crit);
    $style='border-top: 1px solid #7b7b7b ; border-bottom: 1px solid #7b7b7b;
            background-color:#dddddd; padding:4px;';
    $html='<table style="width:50%; border-collapse:collapse;border:1px solid #7b7b7b;">';
    $html.='<tr> <td  style="text-align:center;' . $style . '">' . pq_ucfirst(i18n('assignedResourceList')) . '</td> </tr>';
    foreach ($linkAss as $link) {
      $html.='<tr><td style="width:70%;border: 1px solid #7b7b7b; padding:4px;">' . SqlList::getNameFromId('Affectable', $link->idResource) . '</td></tr>';
    }
    return $html . '</table>';
  }

  function getLinksHtmlTab() {
    $link=new Link();
    $class=get_class($this);
    $id=$this->id;
    $crit=" (ref1Type='$class' and ref1Id=$id ) or (ref2Type='$class' and ref2Id=$id )";
    $linkList=$link->getSqlElementsFromCriteria(null, null, $crit);
    $style='border-top: 1px solid #7b7b7b ; border-bottom: 1px solid #7b7b7b;
            background-color:#dddddd; padding:4px;';
    $html='<table style="width:95%; border-collapse:collapse;border:1px solid #7b7b7b;">
          <tr>' . '<td style="' . $style . '" width="12%"></td>
          <td  style="' . $style . ' text-align:center;" width="76%">Linked Items</td>
          <td  style="' . $style . '" width="12%"></td>
          </tr>';
    $html.='<tr>' . '<td style="' . $style . '">' . pq_ucfirst(i18n('colType')) . '</td>
          <td  style="' . $style . '">' . pq_ucfirst(i18n('colName')) . '</td>
          <td  style="' . $style . '">' . pq_ucfirst(i18n('Status')) . '</td>
          </tr>';

    $status='';
    foreach ($linkList as $link) {
      if ($class==$link->ref1Type and $id==$link->ref1Id) {
        $obj=new $link->ref2Type($link->ref2Id, true);
      } else {
        $obj=new $link->ref1Type($link->ref1Id, true);
      }
      $goto=$obj->getReferenceUrl();
      $html.='<tr><td style="border: 1px solid #7b7b7b; padding:4px;"><a href="' . $goto . '">' . i18n(get_class($obj)) . ' #' . $obj->id . '</a></td>' . '<td style="border: 1px solid #7b7b7b; padding:4px;">' . $obj->name . '</td>';
      if (property_exists($obj, 'idStatus')) 
      // $status = colorNameFormatter(SqlList::getNameFromId('Status', $obj->idStatus) . "#split#" .
      // SqlList::getFieldFromId('Status', $obj->idStatus, 'color'));
      $status=htmlDisplayColoredFull(SqlList::getNameFromId('Status', $obj->idStatus), SqlList::getFieldFromId('Status', $obj->idStatus, 'color'));
      $html.='<td style="border: 1px solid #7b7b7b; padding:0;margin:0">' . $status . '</td></tr>';
      $status='';
    }
    return $html . '</table>';
  }

  // florent ticket 4790
  function getNotesClassicTab($msg, $rowStart, $rowEnd, $sectionStart, $sectionEnd, $labelStart, $labelEnd, $fieldStart, $fieldEnd) {
    $msg.=$rowStart . $sectionStart . '<table style="float:left;"><tr>';
    $msg.='<td>&nbsp;</td>';
    $base=(Parameter::getGlobalParameter('paramAdditionImage')=='YES')?'..':SqlElement::getBaseUrl();
    $msg.='<td><img style="float:left;width:22px; height:22px;" src="' . $base . '/view/css/customIcons/new/iconEmailNotes.png" /></td>';
    $msg.='<td>&nbsp;</td>';
    $msg.='<td style="color: #FFFFFF;font-size:14pt;font-weight:normal;font-family:Verdana,Arial,Helvetica,sans-serif">' . i18n('sectionNote') . '</td>';
    $msg.='<td style="width:90%;">&nbsp;</td>';
    $msg.='</tr></table>' . $sectionEnd . $rowEnd;
    $msg.=$rowStart . '<td><br></td>' . $rowEnd;
    $note=new Note();
    $notes=$note->getSqlElementsFromCriteria(array('refType'=>get_class($this), 'refId'=>$this->id), false, null, 'id desc');
    foreach ($notes as $note) {
      if ($note->idPrivacy==1) {
        $userId=$note->idUser;
        $userName=SqlList::getNameFromId('Affectable', $userId);
        $creationDate=$note->creationDate;
        $updateDate=$note->updateDate;
        if ($updateDate==null) {
          $updateDate='';
        }
        $msg.=$rowStart . $labelStart;
        $msg.='<b>' . $userName . '&nbsp;&nbsp;</b><br>';
        if ($updateDate) {
          $msg.='<i>' . htmlFormatDateTime($updateDate, false, false, false) . '</i>';
        } else {
          $msg.=htmlFormatDateTime($creationDate, false, false, false);
        }
        $msg.=$labelEnd . $fieldStart;
        // $msg.=htmlEncode($note->note,'print');
        $text=new Html2Text($note->note);
        $plainText=$text->getText();
        if (pq_mb_strlen($plainText)>10000 and Parameter::getGlobalParameter('paramAdditionImage')!='YES') { // Should not send too long email
          $noteTruncated=nl2br(pq_mb_substr($plainText, 0, 10000));
          $msg.=htmlSetClickableImages($noteTruncated, 450, true);
        } else {
          $msg.=htmlSetClickableImages($note->note, 450, true);
        }
        $msg.=$fieldEnd . $rowEnd;
      }
    }
    return $msg;
  }

  function getNotesHtmlTab() {
    $html='';
    $note=new Note();
    $critArray=array('refType'=>get_class($this), 'refId'=>$this->id, 'idPrivacy'=>'1');
    $order=Parameter::getGlobalParameter("paramOrderNoteMail");
    $noteList=$note->getSqlElementsFromCriteria($critArray);
    if ($order=='ASC') {
      arsort($noteList);
    }
    $style='border-top: 1px solid #7b7b7b ; border-bottom: 1px solid #7b7b7b;
            background-color:#dddddd; padding:4px;';
    $html='<table style="width:95%; border-collapse:collapse;border:1px solid #7b7b7b;">
          <tr>' . '<td style="' . $style . '" width="12%"></td>
          <td  style="' . $style . ' text-align:center;" width="76%">Notes</td>
          <td  style="' . $style . '" width="12%"></td>
          </tr>';
    $html.='<tr>' . '<td style="' . $style . '">' . pq_ucfirst(i18n('colId')) . '</td>
          <td  style="' . $style . '">' . pq_ucfirst(i18n('colName')) . '</td>
          <td  style="' . $style . '">' . pq_ucfirst(i18n('colDate')) . '</td>
          </tr>';
    $status='';
    foreach ($noteList as $note) {
      $html.='<tr><td style="border: 1px solid #7b7b7b; padding:4px;">' . $note->id . '</td>' . '<td style="border: 1px solid #7b7b7b; padding:4px;">' . 
      // . wordwrap($note->note, 50, '<wbr>', false)
      $note->note . '</td>';
      if (property_exists($note, 'updateDate') and $note->updateDate!='') $date=$note->updateDate;
      else if (property_exists($note, 'creationDate') and isset($note->creationDate)) $date=$note->creationDate;
      $html.='<td style="border: 1px solid #7b7b7b; padding:4px;">' . $date . '</td></tr>';
    }
    return $html . '</table>';
  }

  /*
   * Fill a mail or a title mail template (EmailTemplate class),
   * with properties of the "mailable" object, by replacing "${property}"
   * by the property and "${HISTORY} by a table representing the last changes
   * of the object. ${LINK} and ${NOTE} by a table displaying links and notes
   */
  public function getMailDetailFromTemplate($templateToReplace, $lastChangeDate=null, $isTitle=false) {
    global $lastEmailChangeDate;
    $lastEmailChangeDate=$lastChangeDate;
    $templateToReplace=$this->parseMailMessage($templateToReplace);
    $ref=$this->getReferenceUrl();
    $replyMail=i18n("replyToMail");
    $inputmailboxTicket=new InputMailboxTicket();
    $countInputMailBox=$inputmailboxTicket->countSqlElementsFromCriteria(array('idle'=>'0'));
    if (((Parameter::getGlobalParameter('cronCheckEmailsHost')!='' and Parameter::getGlobalParameter('cronCheckEmails')>0) or $countInputMailBox>0) and !$isTitle) {
      $templateToReplace="
          <table style='font-size:14pt; width: 95%;font-family: Verdana, Arial, Helvetica, sans-serif;'><tr><td style='background:#555555;color: #FFFFFF; text-align: center;'>
          <div style='background:#F0F0F0;color:#A0A0A0;font-style:italic;font-size:80%'>" . htmlEncode($replyMail) . "</div><div style='background:#F0F0F0;color:#F0F0F0;font-size:1pt;'>###PROJEQTOR###</div>
          <a href='" . $ref . "' target='#' style='color:white;display:none;'>" . i18n(get_class($this)) . " #" . htmlEncode($this->id) . "</a></td></tr></table>" . $templateToReplace;
    }

    return preg_replace_callback('(\$\{[a-zA-Z0-9_\-]+\})', function ($matches) {
      global $lastEmailChangeDate;
      $property=pq_trim($matches[0], '${}');
      if (property_exists($this, $property)) {
        if (isset($this, $property) and $this->$property!='') {
          if (pq_substr($property, -8)=='DateTime') {
            return htmlFormatDateTime($this->$property, false, true);
          } else if (pq_substr($property, -4)=='Date') {
            return htmlFormatDate($this->$property, true);
          } else if (isset($this->$property) and is_object($this->$property)) {
            $obj=$this->$property;
            if ($obj->id) {
              if (property_exists($obj, 'refType')) $refType=$obj->refType;
              if (property_exists($obj, 'originType')) $refType=$obj->originType;
              if (property_exists($obj, 'refId')) $refId=$obj->refId;
              if (property_exists($obj, 'originId')) $refId=$obj->originId;
              $refObj=$obj;
              if ($refType and $refId) {
                $refObj=new $refType($refId, true);
              }
              $refClass=i18n(get_class($refObj));
              return $refClass . ' # ' . $refObj->id . ' - ' . $refObj->name;
            } else {
              return '-';
            }
          } else {
            return $this->$property;
          }
        } else {
          return "-";
        }
      } else if (pq_substr($property, 0, 4)=='name' and $property!='name' and pq_substr($property, 4, 1)==pq_strtoupper(pq_substr($property, 4, 1))) {
        $cls=pq_substr($property, 4);
        $fld='id' . $cls;
        if (pq_strpos($property, '__id')>0) {
          $expl=pq_explode('__', $property);
          $cls=pq_substr($expl[1], 2);
        }
        if (property_exists($this, $fld)) {
          if ($cls=='User' or $cls=='Resource' or $cls=='Contact') $cls='Affectable';
          return SqlList::getNameFromId($cls, $this->$fld);
        } else {
          return "\$$fld not a property to define $property of " . get_class($this);
        }
      } else if (pq_substr($property, -4)=='Date' and property_exists($this, $property . 'Time')) {
        $propertyTime=$property . 'Time';
        return htmlFormatDate($this->$propertyTime, true);
      } else if ($property=='responsible' and property_exists($this, 'idResource')) {
        return SqlList::getNameFromId('Affectable', $this->idResource);
      } else if ($property=='dbName') {
        return Parameter::getGlobalParameter('paramDbName');
      } else if ($property=='goto') {
        $goto=$this->getReferenceUrl();
        return '<a href="' . $goto . '">' . i18n(get_class($this)) . ' #' . $this->id . '</a>';
      } else if ($property=="project") {
        if (property_exists($this, 'idProject')) {
          return SqlList::getNameFromId('Project', $this->idProject);
        } else {
          return "-";
        }
      } else if ($property=='ASSIGNMENT') {
        return $this->getAssignmentHtmlTab();
      } else if ($property=='sender') {
        return SqlList::getNameFromId('Affectable', getCurrentUserId());
      } else if ($property=='url') {
        return $this->getReferenceUrl();
      } else if ($property=='HISTORY') {
        return $this->getLastChangeTabForObject($this, $lastEmailChangeDate);
      } else if ($property=='HISTORYFULL') {
        return $this->getLastChangeTabForObject($this, 'full');
      } else if ($property=='LINK') {
        return $this->getLinksHtmlTab();
      } else if ($property=='NOTE') {
        return $this->getNotesHtmlTab();
      } else if ($property=='NOTESTD') {
        // florent
        $rowStart='<tr>';
        $rowEnd='</tr>';
        $labelStart='<td style="background:#DDDDDD;font-weight:bold;text-align: right;width:25%;vertical-align: middle;">&nbsp;&nbsp;';
        $labelEnd='&nbsp;</td>';
        $fieldStart='<td style="width:2px;">&nbsp;</td><td style="background:#FFFFFF;text-align: left;">';
        $fieldEnd='</td>';
        $sectionStart='<td colspan="3" style="background:#555555;color: #FFFFFF; text-align: center;font-size:10pt;font-weight:normal;">';
        $sectionEnd='</td>';
        $notes='<table style="font-size:9pt; width: 95%;font-family: Verdana, Arial, Helvetica, sans-serif;">';
        $notes=$this->getNotesClassicTab($notes, $rowStart, $rowEnd, $sectionStart, $sectionEnd, $labelStart, $labelEnd, $fieldStart, $fieldEnd);
        $notes.='</table>';
        return $notes;
        // gautier #4046
      } else if (pq_substr($property, 0, 15)=='PlanningElement') {
        $className=get_class($this) . 'PlanningElement';
        $itemName=pq_substr($property, 16);
        if (pq_substr($property, -8)=='DateTime') {
          return htmlFormatDateTime($this->$className->$itemName, false, true);
        } else if (pq_substr($property, -4)=='Date') {
          return htmlFormatDate($this->$className->$itemName, true);
        } elseif (pq_substr($property, -4)=='Cost') {
          $value=$this->$className->$itemName;
          if (!$value) $value=0;
          return costFormatter($value);
        } elseif (pq_substr($property, -9)=='CostLocal') {
          $value=$this->$className->$itemName;
          if (!$value) $value=0;
          return costFormatterLocal($value);
        } elseif (pq_substr($property, -4)=='Work') {
          return workFormatter($this->$className->$itemName);
        } elseif (pq_substr($property, -8)=='progress') {
          $percent=$this->$className->$itemName;
          if (!$percent) $percent=0;
          return $percent . '%';
        } elseif (pq_substr($property, -4)=='Rate') {
          $percent=$this->$className->$itemName;
          if (!$percent) $percent=0;
          return $percent . '%';
        } elseif (pq_substr($property, -8)=='Progress') {
          $percent=$this->$className->$itemName;
          if (!$percent) $percent=0;
          return $percent . '%';
        } elseif (pq_substr($property, -3)=='Pct') {
          $percent=$this->$className->$itemName;
          if (!$percent) $percent=0;
          return $percent . '%';
        } else {
          return $this->$className->$itemName;
        }
      } else if (pq_substr($property, 0, 10)=='VotingItem') {
        $itemName=pq_substr($property, 11);
        return $this->VotingItem->$itemName;
      } else if (pq_substr($property, 0, 11)=='WorkElement') {
        $itemName=pq_substr($property, 12);
        if (pq_substr($property, -8)=='DateTime') {
          return htmlFormatDateTime($this->WorkElement->$itemName, false, true);
        } else if (pq_substr($property, -4)=='Date') {
          return htmlFormatDate($this->WorkElement->$itemName, true);
        } elseif (pq_substr($property, -4)=='Cost') {
          return costFormatter($this->WorkElement->$itemName);
        } elseif (pq_substr($property, -4)=='Work') {
          return workFormatter($this->WorkElement->$itemName);
        } elseif (pq_substr($property, -4)=='Rate') {
          return $this->WorkElement->$itemName . '%';
        } else {
          return $this->WorkElement->$itemName;
        }
      } else if ($property=='allAttachments') {
        return;
      } else if ($property=='lastAttachment') {
        return;
      } else {
        return "\$$property not a property of " . get_class($this);
      }
    }, pq_nvl($templateToReplace));
  }

  public function getReferenceUrl() {
    $ref=self::getBaseUrl();
    $ref.='/view/main.php?directAccess=true&objectClass=' . get_class($this) . '&objectId=' . $this->id;
    return $ref;
  }

  /**
   * =========================================================================
   * Specific function added to setup a workaround for bug #305
   * waiting for Dojo fixing (Dojo V1.6 ?)
   *
   * @todo : deactivate this function if Dojo fixed.
   */
  public function recalculateCheckboxes($force=false) {
    if (!property_exists($this, 'idStatus')) {
      return;
    }
    // If $_skipAllControls is set, must not update checkboxes
    // if (self::$_skipAllControls==="checkboxes") return;
    $status=new Status($this->idStatus);
    $class=get_class($this);
    // if ($class=='TicketSimple') $class='Ticket';
    // $fldType = 'id' . $class . 'Type';
    $fldType=self::getTypeName($class);
    // $typeClass = $class . 'Type';
    $typeClass=self::getTypeClassName($class);
    if (!property_exists($this, $fldType)) {
      return;
    }
    $type=new $typeClass($this->$fldType, true);
    if (((property_exists($type, 'lockHandled') and $type->lockHandled) or $force)) {
      if (property_exists($this, 'handled')) {
        if ($status->setHandledStatus) {
          $this->handled=1;
          if (property_exists($this, 'handledDate') and !$this->handledDate) $this->handledDate=date("Y-m-d");
          if (property_exists($this, '_Assignment') and $this->_Assignment!=null) {
            foreach ($this->_Assignment as $id=>$ass) {
              if (isset($ass->realStartDate)) {
                $this->handledDate=$ass->realStartDate;
              }
            }
          }
          if (property_exists($this, 'handledDateTime') and !$this->handledDateTime) $this->handledDateTime=date("Y-m-d H:i:s");
        } else {
          if (property_exists($this, 'handledDate') and $this->handledDate and $this->handled==1) $this->handledDate=null;
          if (property_exists($this, 'handledDateTime') and $this->handledDateTime and $this->handled==1) $this->handledDateTime=null;
          $this->handled=0;
        }
      } else if (property_exists($this, 'isStarted')) {
        if ($status->setHandledStatus) {
          $this->isStarted=1;
          if (property_exists($this, 'realStartDate') and !$this->realStartDate) $this->realStartDate=date("Y-m-d");
        }
      }
    }
    if (((property_exists($type, 'lockPaused') and $type->lockPaused) or $force)) {
      if (property_exists($this, 'paused')) {
        if ($status->setPausedStatus) {
          $this->paused=1;
          if (property_exists($this, 'WorkElement') and ($this->WorkElement??false) and $this->WorkElement->ongoing) $this->WorkElement->stop();
          if (property_exists($this, 'pausedDateTime') and !$this->pausedDateTime) $this->pausedDateTime=date("Y-m-d H:i:s");
          if (property_exists($this, 'done')) $this->done=0;
        } else {
          $this->paused=0;
          if (property_exists($this, 'fixPlanning')) $this->fixPlanning=0;
        }
      }
    }
    if (((property_exists($type, 'lockDone') and $type->lockDone) or $force)) {
      if (property_exists($this, 'done')) {
        if ($status->setDoneStatus) {
          $this->done=1;
          if (property_exists($this, 'doneDate') and !$this->doneDate) $this->doneDate=date("Y-m-d");
          if (property_exists($this, 'doneDateTime') and !$this->doneDateTime) $this->doneDateTime=date("Y-m-d H:i:s");
        } else {
          if (property_exists($this, 'doneDate') and $this->doneDate and $this->done==1) $this->doneDate=null;
          if (property_exists($this, 'doneDateTime') and $this->doneDateTime and $this->done==1) $this->doneDateTime=null;
          $this->done=0;
        }
      } else if (property_exists($this, 'isDelivered')) {
        if ($status->setDoneStatus) {
          $this->isDelivered=1;
          if (property_exists($this, 'realDeliveryDate') and !$this->realDeliveryDate) $this->realDeliveryDate=date("Y-m-d");
        }
      }
    }
    if (((property_exists($type, 'lockSolved') and $type->lockSolved) or $force) and property_exists($this, 'solved') and property_exists($this, 'idResolution')) {
      $resolution=new Resolution($this->idResolution);
      if ($resolution->solved) {
        $this->solved=1;
      } else {
        $this->solved=0;
      }
    }
    if (((property_exists($type, 'lockIdle') and $type->lockIdle) or $force) and property_exists($this, 'idle')) {
      if (!self::isSaveConfirmed() or $force) { // PBER add or $force to enable change on Multiple Update.
        if ($status->setIdleStatus) {
          $this->idle=1;
          if (property_exists($this, 'idleDate') and !$this->idleDate) $this->idleDate=date("Y-m-d");
          if (property_exists($this, 'idleDateTime') and !$this->idleDateTime) $this->idleDateTime=date("Y-m-d H:i:s");
          // BEGIN - ADD qCazelles #187
          if (property_exists($this, 'realEndDate') and !$this->realEndDate) $this->realEndDate=date("Y-m-d");
          // END -ADD qCazelles #187
        } else {
          if (property_exists($this, 'idleDate') and property_exists($this, 'done') and $this->idleDate and $this->done==1) $this->idleDate=null;
          if (property_exists($this, 'idleDateTime') and property_exists($this, 'done') and $this->idleDateTime and $this->done==1) $this->idleDateTime=null;
          if (property_exists($this, 'realEndDate') and property_exists($this, 'done') and $this->realEndDate and $this->done==1) $this->realEndDate=null;
          $this->idle=0;
        }
      }
    }
    if (((property_exists($type, 'lockCancelled') and $type->lockCancelled) or $force) and property_exists($this, 'cancelled')) {
      $this->cancelled=($status->setCancelledStatus)?1:0;
    }
    if (((property_exists($this, 'lockIntoService') and $type->lockIntoService) or $force) and property_exists($this, 'isEis')) {
      if ($status->setIntoserviceStatus) {
        $this->isEis=1;
        if (property_exists($this, 'realEisDate') and !$this->realEisDate) $this->realEisDate=date("Y-m-d");
      }
    }
  }

  public function getAlertLevel($withIndicator=false, $isToday=false) {
    $crit=array('refType'=>get_class($this), 'refId'=>$this->id);
    $indVal=new IndicatorValue();
    $lst=$indVal->getSqlElementsFromCriteria($crit, false);
    $level="NONE";
    $globalLevel="NONE";
    $desc='';
    $i=0;
    foreach ($lst as $indVal) {
      $level="NONE";
      if ($indVal->warningSent) {
        $level="WARNING"; // Over warning value
        if ($globalLevel!="ALERT") $globalLevel="WARNING";
      }
      if ($indVal->alertSent) {
        $level="ALERT"; // Over alert value
        $globalLevel="ALERT";
      }
      if ($indVal->status=="KO") {
        // $level="OVER"; // Over target value
      }
      if ($withIndicator and ($indVal->warningSent or $indVal->alertSent)) {
        if ($desc=='') {
          if (!$isToday) {
            $desc.='<table>';
            $desc.='<tr><td>';
          }
          $desc.='<div style="font-size:80%;color:#555555;">' . i18n('colIdIndicator') . '&nbsp;</div>';
          if (!$isToday) {
            $desc.='</td><td><div style="font-size:80%;color:#555555;padding-left:10px;">' . i18n('colTargetValue') . '&nbsp;</div></td>';
            $desc.='<td><div style="font-size:80%;color:#555555;padding-left:10px;">' . i18n('colWarningValue') . '&nbsp;</div></td>';
          }
          if (!$isToday) {
            $desc.='</tr>';
          }
        }
        $color=($indVal->alertSent)?"#FFAAAA":"#FFDDAA";
        if (!$isToday) {
          $desc.='<tr style="background-color:' . $color . ';padding:2px 5px;margin:3px 0px 2px 0px;border:1px solid #aaaaaa;"><td>';
          $desc.='<div style="font-size:80%;">' . $indVal->getShortDescription();
        } else {
          $desc.='<div style="font-size:80%;background-color:' . $color . ';padding:2px 5px;margin:3px 0px 2px 0px;border:1px solid #aaaaaa;">' . $indVal->getShortDescription();
        }
        $desc.='</div>';
        if (!$isToday) {
          $desc.='</td>';
          $indDesc=$indVal->getShortDescriptionArray();
          $desc.='<td style="font-size:80%;padding-left:10px;">';
          $desc.=$indDesc['target'];
          $desc.='</td>';
          $desc.='<td style="font-size:80%;padding-left:10px;">';
          if ($indVal->alertSent) {
            $desc.=$indDesc['alert'];
          } else {
            $desc.=$indDesc['warning'];
          }
          // $desc.='</div>';
          $desc.='</td>';
          $desc.='</tr>';
          $i++;
        }
      }
    }
    if (!$isToday) {
      if ($i!=0) {
        $desc.='</table>';
      }
    }
    return array('level'=>$globalLevel, 'description'=>$desc);
  }

  public function buildSelectClause($included=false, $hidden=array(), $dep=array(), $parent=null) {
    global $outMode;
    $table=$this->getDatabaseTableName();
    $select="";
    $from="";
    if (self::is_subclass_of($this, 'PlanningElement')) {
      $this->setVisibility();
    }
    foreach ($this as $col=>$val) {
      $firstCar=pq_substr($col, 0, 1);
      $threeCars=pq_substr($col, 0, 3);
      $testCol=$col;
      if (isset($outMode) and $outMode!="csv") {
        if ($col=='inheritedEndDate' and Parameter::getGlobalParameter('gestionInheritedEndDate')!='NO') $testCol='validatedEndDate';
      }
      if (!isset($dep[$col]) and !isset($dep['root']) and (($included and ($col=='id' or $threeCars=='ref' or $threeCars=='top' or $col=='idle')) or ($firstCar=='_') or ($this->isAttributeSetToField($testCol, 'hidden') and !$this->isAttributeSetToField($testCol, 'forceExport') and $col!='id') or ($col=='password') or (isset($hidden[$testCol])) or (pq_strpos($this->getFieldAttributes($testCol), 'noExport')!==false) or (pq_strpos($this->getFieldAttributes($col), 'calculated')!==false))) 
      // or ($costVisibility!="ALL" and self::isAmount($col) )
      // or ($workVisibility!="ALL" and self::isWork($col) )
      // or calculated field : not to be fetched
      {
        // Here are all cases of not dispalyed fields
      } else if ($included and ((isset($dep['root']) and isset($hidden[$dep['root'] . $col])) or ($parent and ($col=='refType' or $col=='refId' or $col=='id' . $parent)))) {
        //
      } else if ($this->isAttributeSetToField($col, 'noExport') or $this->isAttributeSetToField($col, 'calculated')) {
        //
      } else if ($firstCar==pq_ucfirst($firstCar) or isset($dep[$col])) {
        $classDep=pq_ltrim($col, '_');
        if (!SqlElement::class_exists($classDep)) continue;
        $ext=new $classDep();
        if (isset($dep[$col])) {
          $cpt=0;
          foreach ($ext as $tstCol=>$tstVal) {
            if (!isset($hidden[$classDep . '_' . $tstCol]) and pq_substr($tstCol, 0, 1)!='_' and $tstCol!='refType' and $tstCol!='refId' and $tstCol!='id' . get_class($this)) {
              $cpt++;
            }
          }
          if ($cpt==0) continue;
        }
        if ((property_exists($classDep, 'refType') and property_exists($classDep, 'refId')) or property_exists($classDep, 'id' . get_class($this))) {
          $from.=' left join ' . $ext->getDatabaseTableName();
          if (property_exists($classDep, 'refType') and property_exists($classDep, 'refId')) {
            $from.=' on ' . $table . ".id" . ' = ' . $ext->getDatabaseTableName() . '.refId' . ' and ' . $ext->getDatabaseTableName() . ".refType='" . get_class($this) . "'";
          } else if (property_exists($classDep, 'id' . get_class($this))) {
            $from.=" on $table.id=" . $ext->getDatabaseTableName() . ".id" . get_class($this);
            if ($classDep=='DocumentVersion' and isset($hidden['documentVersionAll'])) {
              $from.=" and $table.idDocumentVersion=" . $ext->getDatabaseTableName() . ".id";
            }
          }
          if (isset($dep[$col])) {
            $extClause=$ext->buildSelectClause(true, $hidden, array('root'=>$classDep . '_'), get_class($this));
          } else {
            $extClause=$ext->buildSelectClause(true, $hidden);
          }
          if (pq_trim($extClause['select'])) {
            $select.=', ' . $extClause['select'];
          }
        }
      } else {
        $select.=($select=='')?'':', ';
        $root=($included and isset($dep['root']))?pq_strtolower($dep['root']):'';
        $select.=$table . '.' . $this->getDatabaseColumnName($col) . ' as ' . $root . $col;
      }
    }
    return array('select'=>$select, 'from'=>$from);
  }

  public function setReference($force=false, $old=null, $fmtPrefix=null, $fmtSuffix=null, $fmtNumber=null) {
    scriptLog('SqlElement::setReference');
    $objectsWithFixedReference=array('Bill');
    if (!property_exists($this, 'reference')) {
      return;
    }
    $class=get_class($this);
    if ($class=='TicketSimple') $class='Ticket';
    if ($class=='Bill' and !$this->billId) return; // Do not set Reference until billId is set

    if (!$fmtPrefix) $fmtPrefix=Parameter::getGlobalParameter('referenceFormatPrefix');
    if (!$fmtSuffix) $fmtSuffix='';
    if (!$fmtNumber) $fmtNumber=Parameter::getGlobalParameter('referenceFormatNumber');
    if ($class=='Bill') {
      $fmtPrefixBill=Parameter::getGlobalParameter('billReferenceFormat');
      $fmtNumberBill=Parameter::getGlobalParameter('billNumSize');
      if ($fmtPrefixBill) $fmtPrefix=$fmtPrefixBill;
      if ($fmtNumberBill) $fmtNumber=$fmtNumberBill;
    }
    $posNume=pq_strpos($fmtPrefix, '{NUME}');
    if ($posNume!==false) {
      $fmtSuffix=pq_substr($fmtPrefix, $posNume+6);
      $fmtPrefix=pq_substr($fmtPrefix, 0, $posNume);
    }
    $change=Parameter::getGlobalParameter('changeReferenceOnTypeChange');
    // $type = 'id' . $class . 'Type';
    $type=self::getTypeName($class);
    if ($this->reference and !$force) {
      if ($change!='YES') {
        return;
      }
      if (!property_exists($this, $type)) {
        return;
      }
      if (!property_exists($this, 'idProject')) {
        return;
      }
      if (!$old) {
        $old=new $class($this->id, true);
      }
      if (!property_exists($this, 'idProduct')) {
        if ($this->$type==$old->$type and $this->idProject==$old->idProject) {
          return;
        }
      } else {
        if ($this->$type==$old->$type and $this->idProject==$old->idProject and $this->idProduct==$old->idProduct) {
          return;
        }
      }
      if (in_array(get_class($this), $objectsWithFixedReference)) {
        return;
      }
    }
    if (isset($this->idProject)) {
      $projObj=new Project($this->idProject, true);
    } else {
      $projObj=new Project();
    }
    if (property_exists($this, 'idProduct') and isset($this->idProduct)) {
      $prodObj=new Product($this->idProduct, true);
    } else {
      $prodObj=new Product();
    }
    if (isset($this->$type)) {
      $typeObj=new Type($this->$type);
    } else {
      $typeObj=new Type();
    }
    $orga=new Organization();
    if (property_exists($this, 'idProject')) $proj=new Project($this->idProject, true);
    if (property_exists($proj, 'idOrganization')) $orga=new Organization($proj->idOrganization, true);

    $year=date('Y');
    $month=date('m');
    if (get_class($this)=='Bill') {
      $year=pq_substr($this->date, 0, 4);
      $month=pq_substr($this->date, 5, 2);
    } else if (property_exists($this, 'sendDate') and $this->sendDate) {
      $year=pq_substr($this->sendDate, 0, 4);
      $month=pq_substr($this->sendDate, 5, 2);
    } else if (property_exists($this, 'creationDate')) {
      $year=pq_substr($this->creationDate, 0, 4);
      $month=pq_substr($this->creationDate, 5, 2);
    } else if (property_exists($this, 'creationDateTime')) {
      $year=pq_substr($this->creationDateTime, 0, 4);
      $month=pq_substr($this->creationDateTime, 5, 2);
    }
    $arrayFrom=array('{PROD}', '{PROJ/PROD}', '{PROD/PROJ}', '{PROJ}', '{TYPE}', '{ORGA}', '{YEAR}', '{MONTH}');
    $arrayTo=array(
        $prodObj->designation,
        ($projObj->projectCode)?$projObj->projectCode:$prodObj->designation,
        ($prodObj->designation)?$prodObj->designation:$projObj->projectCode,
        $projObj->projectCode,
        $typeObj->code,
        $orga->organizationCode,
        $year,
        $month);
    $prefix=pq_str_replace($arrayFrom, $arrayTo, $fmtPrefix);
    $suffix=pq_str_replace($arrayFrom, $arrayTo, $fmtSuffix);
    $query="select max(reference) as ref from " . $this->getDatabaseTableName();
    $query.=" where reference like '" . $prefix . "%'";
    $query.=" and length(reference)=( select max(length(reference)) from " . $this->getDatabaseTableName();
    $query.=" where reference like '" . $prefix . "%')";
    $ref=$prefix;
    $mutex=new Mutex($prefix);
    $mutex->reserve();
    $result=Sql::query($query);
    $numMax='0';
    if ($result) {
      $line=Sql::fetchLine($result);
      $refMax=$line['ref'];
      $numMax=intval(pq_substr($refMax, pq_strlen($prefix)));
    }
    $numMax+=1;
    if ($fmtNumber and $fmtNumber-pq_strlen($numMax)>0) {
      $num=pq_substr('0000000000', 0, $fmtNumber-pq_strlen($numMax)) . $numMax;
    } else {
      $num=$numMax;
    }
    $this->reference=$prefix . $num . $suffix;
    if (get_class($this)=='Document' and property_exists($this, 'documentReference')) {
      $fmtDocument=Parameter::getGlobalParameter('documentReferenceFormat');
      $docRef=pq_str_replace(array('{PROD}', '{PROJ/PROD}', '{PROD/PROJ}', '{PROJ}', '{TYPE}', '{ORGA}', '{NUM}', '{NAME}'), array(
          $prodObj->designation,
          ($projObj->projectCode)?$projObj->projectCode:$prodObj->designation,
          ($prodObj->designation)?$prodObj->designation:$projObj->projectCode,
          $projObj->projectCode,
          $typeObj->code,
          $orga->organizationCode,
          $num,
          $this->name), $fmtDocument);
      $this->documentReference=$docRef;
    }
    if ($force) {
      $this->updateSqlElement();
    }
    $mutex->release();
  }

  public function setDefaultResponsible() {
    if (get_class($this)!='Project' and property_exists($this, 'idResource') and property_exists($this, 'idProject') and !pq_trim($this->idResource) and pq_trim($this->idProject)) {
      if (Parameter::getGlobalParameter('setResponsibleIfSingle')=="YES") {
        $aff=new Affectation();
        $crit=array('idProject'=>$this->idProject);
        $cpt=$aff->countSqlElementsFromCriteria($crit);
        if ($cpt==1) {
          $aff=SqlElement::getSingleSqlElementFromCriteria('Affectation', $crit);
          $res=new Resource($aff->idResource, true);
          if ($res and $res->id) {
            $this->idResource=$res->id;
          }
        }
      }
    } else if (!$this->id and property_exists($this, 'idResource') and !property_exists($this, 'idProject') and !pq_trim($this->idResource)) {
      // On creation, if acces right for non project dependant item on update is "Responsible", auto set responsible to self
      $accessRight=securityGetAccessRight('menu' . get_class($this), 'update', null, getSessionUser());
      if ($accessRight=='RES') $this->idResource=getCurrentUserId();
    }
  }

  public function getTitle($col) {
    if ($this->getFieldTooltip($col)) return ''; // If field has hint, don't show title

    $arrayTest=array('title', 'col', '');
    foreach ($arrayTest as $testPrefix) {
      $test=$testPrefix . pq_ucfirst($col);
      $testTranslation=i18n($test);
      if ($testTranslation!="[$test]") return $testTranslation;
    }
    return i18n($col);
  }

  public static function unsetRelationShip($rel1, $rel2) {
    unset(self::$_relationShip[$rel1][$rel2]);
  }

  public function getOld($withoutDependingElemnts=true) {
    $class=get_class($this);
    return new $class($this->id, $withoutDependingElemnts);
  }

  public function splitLongFields() {
    $maxLenth=500;
    foreach ($this as $fld=>$val) {
      if ($this->getDataLength($fld)>100 and pq_strlen($val)>$maxLenth) {
        // $secFull="_sec_".$fld;
        // $this->$secFull=$val;
        $fldFull="_" . $fld . "_full";
        $this->$fldFull=$val;
        $this->$fld=pq_substr($val, 0, $maxLenth) . ' (...)';
      }
    }
  }

  public static function isVisibleField($col) {
    // Check if cost and work field is visible for profile
    $cost=(pq_substr($col, -4)=='Cost' or pq_substr($col, -6)=="Amount")?true:false;
    $work=(pq_substr($col, -4)=='Work')?true:false;
    if (!$cost and !$work) {
      return true;
    }
    if (!self::$staticCostVisibility or !self::$staticWorkVisibility) {
      $pe=new PlanningElement();
      $pe->setVisibility();
      self::$staticCostVisibility=$pe->_costVisibility;
      self::$staticWorkVisibility=$pe->_workVisibility;
    }
    $costVisibility=self::$staticCostVisibility;
    $workVisibility=self::$staticWorkVisibility;
    $validated=(pq_substr($col, 0, 9)=='validated')?true:false;
    if ($cost) {
      if ($costVisibility=='ALL') {
        return true;
      } else if ($costVisibility=='NO') {
        return false;
      } else if ($costVisibility=='VAL') {
        if ($validated) {
          return true;
        } else {
          return false;
        }
      } else {
        errorLog("ERROR : costVisibility='$costVisibility' is not 'ALL', 'NO' or 'VAL'");
      }
    } else if ($work) {
      if ($workVisibility=='ALL') {
        return true;
      } else if ($workVisibility=='NO') {
        return false;
      } else if ($workVisibility=='VAL') {
        if ($validated) {
          return true;
        } else {
          return false;
        }
      } else {
        errorLog("ERROR : workVisibility='$workVisibility' is not 'ALL', 'NO' or 'VAL'");
      }
    }
    return true;
  }

  public static function setDeleteConfirmed() {
    self::$staticDeleteConfirmed=true;
  }

  public static function isDeleteConfirmed() {
    return self::$staticDeleteConfirmed;
  }

  public static function setSaveConfirmed() {
    self::$staticSaveConfirmed=true;
  }

  public static function isSaveConfirmed() {
    return self::$staticSaveConfirmed;
  }

  public static function isThumbableField($col) {
    // MTY - LEAVE SYSTEM
    // return ($col == 'idResource' or $col == 'idUser' or $col == 'idContact' or $col=='idAccountable' or $col=='idResponsible') ? true : false;
    return ($col=='idEmployee' or $col=='idResource' or $col=='idUser' or $col=='idContact' or $col=='idAccountable' or $col=='idResponsible' or $col=='idAffectable')?true:false;
    // MTY - LEAVE SYSTEM
  }

  public static function isColorableField($col, $val) {
    if (!$val) return false;
    if (isForeignKey($col, "")) {
      $class=pq_substr(foreignKeyWithoutAlias($col), 2);
      if (property_exists($class, 'color')) return true;
      else return false;
    } else {
      return false;
    }
    // return ($col == 'idStatusNotification' or $col == 'idProject' or $col == 'idStatus' or $col == 'idQuality' or $col == 'idHealth' or $col == 'idTrend' or $col == 'idLikelihood' or $col == 'idCriticality' or $col == 'idSeverity' or $col == 'idUrgency' or $col == 'idPriority' or $col == 'idRiskLevel' or $col == 'idFeasibility' or $col == 'idEfficiency' or $col == 'idResolution' or $col == 'idTenderStatus' or $col == 'idDeliverableWeight' or $col == 'idDeliverableStatus' or $col == 'idIncomingWeight' or $col == 'idIncomingStatus') ? true : false;
  }

  public static function isIconableField($col, $val) {
    if (!$val) return false;
    if (isForeignKey($col, "")) {
      $class=pq_substr(foreignKeyWithoutAlias($col), 2);
      if (property_exists($class, 'icon') and $class!='TemplateReportScope') { // PBER Issue on TemplateReportScope that has field icon, that does not exist in DB
        $forein=new $class($val);
        if ($forein->icon) return true;
        else return false;
      } else
        return false;
    } else {
      return false;
    }
    // return ($col == 'idQuality' or $col == 'idHealth' or $col == 'idTrend' or $col=='idAssetType') ? true : false;
  }

  public function getExtraRequiredFields($newType="", $newStatus="", $newPlanningMode="", $profile=null) {
    global $currenObjectStatus, $currentObjectType, $parentObject;
    $result=array();
    $type=$newType;
    $status=$newStatus;
    $planningMode=$newPlanningMode;
    $user=getSessionUser();
    $class=get_class($this);
    // MTY - LEAVE SYSTEM
    if ($class=="Leave") {
      return $result;
    }
    // MTY - LEAVE SYSTEM
    $testObj=$this;
    $testClass=$class;
    // $typeFld = 'id' . $class . "Type";
    // if ($class=='PeriodicMeeting') $typeFld='idMeetingType';
    $typeFld=self::getTypeName($class);
    if (SqlElement::is_a($this, 'PlanningElement')) {
      if ($this->refType) {
        $testClass=$this->refType;
      } else {
        $testClass=pq_str_replace('PlanningElement', '', $class);
      }
      if ($testClass and SqlElement::class_exists($testClass)) {
        if ($parentObject) $testObj=$parentObject;
        else $testObj=new $testClass($this->refId, true);
      }
      $planningModeName='id' . pq_str_replace('PlanningElement', '', get_class($this)) . 'PlanningMode';
      if (!$planningMode and property_exists($this, $planningModeName)) {
        $planningMode=$this->$planningModeName;
      }
    } else if ($class=='WorkElement') {
      if ($this->refType) {
        $testClass=$this->refType;
      } else {
        $testClass='Ticket';
      }
      if ($testClass and SqlElement::class_exists($testClass)) $testObj=new $testClass($this->refId, true);
    }
    if (!$profile) $profile=$user->getProfile($this);
    if ($this->id) {
      // $typeName = 'id' . pq_str_replace ( 'PlanningElement', '', get_class ( $this ) ) . 'Type';
      $typeName=self::getTypeName(get_class($this));
      $planningModeName='id' . pq_str_replace('PlanningElement', '', get_class($this)) . 'PlanningMode';
      if (!$type and property_exists($testObj, $typeName)) {
        $type=$testObj->$typeName;
      }
      if (!$status and property_exists($testObj, 'idStatus')) {
        $status=$testObj->idStatus;
      }
      if (!$planningMode and property_exists($this, $planningModeName)) {
        $planningMode=$this->$planningModeName;
      }
    } else {
      // $typeName = 'id' . pq_str_replace ( 'PlanningElement', '', get_class ( $this ) ) . 'Type';
      $typeName=self::getTypeName(get_class($this));
      // $typeClassName = pq_str_replace ( 'PlanningElement', '', get_class ( $this ) ) . 'Type';
      $typeClassName=self::getTypeClassName(get_class($this));
      if (!$status) {
        $status=$this->getFirstStatus($type);
      }
      $planningModeName='id' . pq_str_replace('PlanningElement', '', get_class($this)) . 'PlanningMode';
      if (property_exists($this, $typeName) and !$newType) $type=$this->$typeName; // PBER : Removed this line as it blocks update of required fields on creation
      $typeElt=null;
      if (!$type and SqlElement::class_exists($typeClassName) and $typeClassName!="ExpenseDetailType") {
        $typeList=SqlList::getList($typeClassName);
        $typeElt=reset($typeList);
        $type=($typeElt)?key($typeList):null;
      }
      if (!$planningMode and $type and SqlElement::class_exists($typeClassName) and property_exists($typeClassName, $planningModeName)) {
        $typeObj=new $typeClassName($type);
        $planningMode=$typeObj->$planningModeName;
      }
    }
    if ($planningMode and $planningMode!='*' and (!property_exists($this, 'elementary') or $this->elementary or !$this->id) and !self::isCopyInProgress()) {
      $planningModeObj=new PlanningMode($planningMode);
      if ($planningModeObj->mandatoryStartDate and property_exists($this, 'validatedStartDate')) {
        $result['validatedStartDate']='required';
      }
      if ($planningModeObj->mandatoryEndDate and property_exists($this, 'validatedEndDate')) {
        $result['validatedEndDate']='required';
      }
      if ($planningModeObj->mandatoryDuration and property_exists($this, 'validatedDuration')) {
        $result['validatedDuration']='required';
      }
    }
    if ($type and $type!='*') {
      $typeObj=new Type($type);
      if ($typeObj->mandatoryResourceOnHandled) {
        if ($newStatus and $newStatus!='*') {
          $statusObj=new Status($newStatus);
          if ($statusObj->setHandledStatus) {
            $result['idResource']='required';
          }
        } else {
          if (property_exists($this, 'handled') and $this->handled) {
            $result['idResource']='required';
          }
        }
      }
      if ($typeObj->mandatoryDescription) {
        $result['description']='required';
      }
      if ($typeObj->mandatoryResultOnDone) {
        if ($newStatus and $newStatus!='*') {
          $statusObj=new Status($newStatus);
          if ($statusObj->setDoneStatus) {
            $result['result']='required';
          }
        } else {
          if (property_exists($this, 'done') and $this->done) {
            $result['result']='required';
          }
        }
      }
      if (property_exists($typeObj, 'mandatoryResolutionOnDone') and $typeObj->mandatoryResolutionOnDone) {
        if ($newStatus and $newStatus!='*') {
          $statusObj=new Status($newStatus);
          if ($statusObj->setDoneStatus) {
            $result['idResolution']='required';
          }
        } else {
          if (property_exists($this, 'done') and $this->done) {
            $result['idResolution']='required';
          }
        }
      }
    }
    // Add extra result from plugin
    $extraResult=self::getExtraRequiredFieldsFullList();
    $scopeArray=array('Type', 'Status', 'Profile');
    foreach ($scopeArray as $scope) {
      $fld=pq_strtolower($scope);
      if ($$fld and $$fld!='*' and isset($extraResult[$scope][get_class($this)][$$fld])) {
        foreach ($extraResult[$scope][get_class($this)][$$fld] as $field) {
          $result[$field]='required';
        }
      }
    }
    /*
     * // TEST
     * $list=self::getExtraHiddenFieldsFullList();
     * $listType=array();
     * $listStatus=array();
     * $listProfile=array();
     * if ($type and $type!='*') {
     * $type=($newType)?$newType:$testObj->$typeFld;
     * if (isset($list['Type']) and isset($list['Type'][$class]) and isset($list['Type'][$class][$type]) ) {
     * $listType=$list['Type'][$class][$type];
     * }
     * }
     * if (property_exists($testObj,'idStatus') and $newStatus!='*') {
     * $status=($newStatus)?$newStatus:$testObj->idStatus;
     * if (isset($list['Status']) and isset($list['Status'][$class]) and isset($list['Status'][$class][$status]) ) {
     * $listStatus=$list['Status'][$class][$status];
     * }
     * }
     * if ($newProfile!='*') {
     * if ($newProfile) {
     * $profile=$newProfile;
     * } else {
     * $profile=getSessionUser()->getProfile($this);
     * }
     * if (isset($list['Profile']) and isset($list['Profile'][$class]) and isset($list['Profile'][$class][$profile]) ) {
     * $listProfile=$list['Profile'][$class][$profile];
     * }
     * }
     * // TEST
     */

    return $result;
  }

  public function getExtraHiddenFields($newType="", $newStatus="", $newProfile="", $forExport=false) {
    $class=get_class($this);
    // MTY - LEAVE SYSTEM
    if ($class=="Leave") {
      return array();
    }
    // MTY - LEAVE SYSTEM
    $testObj=$this;
    $testClass=$class;
    $typeFld='id' . $class . "Type";
    if (SqlElement::is_a($this, 'PlanningElement')) {
      if ($this->refType) {
        $testClass=$this->refType;
      } else {
        $testClass=pq_str_replace('PlanningElement', '', $class);
      }
      $testObj=new $testClass($this->refId, true);
    } else if ($class=='WorkElement') {
      if ($this->refType) {
        $testClass=$this->refType;
      } else {
        $testClass='Ticket';
      }
      $testObj=new $testClass($this->refId, true);
    }
    // $typeClass = $testClass . 'Type';
    $typeClass=SqlElement::getTypeClassName($testClass);
    // $typeFld = 'id' . $typeClass;
    $typeFld=SqlElement::getTypeName($testClass);
    // if ($class == 'TicketSimple')
    // $typeFld = 'idTicketType';
    $list=self::getExtraHiddenFieldsFullList();
    $listType=array();
    $listStatus=array();
    $listProfile=array();
    $listModule=array();
    if (property_exists($testObj, $typeFld) and $newType!='*') {
      $type=($newType)?$newType:$testObj->$typeFld;
      if (isset($list['Type']) and isset($list['Type'][$class]) and isset($list['Type'][$class][$type])) {
        $listType=$list['Type'][$class][$type];
      }
    }
    if (property_exists($testObj, 'idStatus') and $newStatus!='*') {
      $status=($newStatus)?$newStatus:$testObj->idStatus;
      if (!$status) {
        $status=$this->getFirstStatus($newType);
      }
      if (isset($list['Status']) and isset($list['Status'][$class]) and isset($list['Status'][$class][$status])) {
        $listStatus=$list['Status'][$class][$status];
      }
    }
    if ($newProfile!='*') {
      if ($newProfile) {
        $profile=$newProfile;
      } else {
        $profile=getSessionUser()->getProfile($this);
      }
      if (isset($list['Profile']) and isset($list['Profile'][$class]) and isset($list['Profile'][$class][$profile])) {
        $listProfile=$list['Profile'][$class][$profile];
      }
    }
    // if ($newStatus=='*' and $newProfile=='*') return $listType;
    // if ($newType=='*' and $newProfile=='*') return $listStatus;
    // if ($newType=='*' and $newStatus=='*') return $listProfile;
    $currentScript=basename($_SERVER['PHP_SELF'], '.php');
    if (pq_substr($currentScript, 0, 19)=="screenCustomization") {
      $listModule=array();
    } else {
      $listModule=Module::getListOfFieldsToHide($class);
    }

    // if ($forExport) return array_unique ( $listProfile);
    if ($forExport) return array_merge($listProfile, $listModule);
    return array_unique(array_merge($listType, $listStatus, $listProfile, $listModule));
  }

  private static function getExtraRequiredFieldsFullList() {
    if (self::$_extraRequiredFields!=null) {
      return self::$_extraRequiredFields;
    }
    $sessionList=getSessionValue('extraRequiredFieldsArray');
    if ($sessionList) {
      self::$_extraRequiredFields=$sessionList;
      return self::$_extraRequiredFields;
    }
    $extra=new ExtraRequiredField();
    $extraList=$extra->getSqlElementsFromCriteria(null); // Get all fields
    $result=array('Type'=>array(), 'Status'=>array(), 'Profile'=>array()); // Only scope for Type, Status, Profile
    foreach ($extraList as $extra) {
      $sp=pq_explode('#', $extra->scope);
      if (count($sp)!=2) return array();
      $scope=$sp[0];
      $class=$sp[1];
      if (!isset($result[$scope])) {
        errorLog("getExtraRequiredFieldsFullList() : some data has scope '$scope' different from Type, Status, Profile");
        return array();
      }
      if (!isset($result[$scope][$class])) $result[$scope][$class]=array();
      if (!isset($result[$scope][$class][$extra->idType])) $result[$scope][$class][$extra->idType]=array();
      $result[$scope][$class][$extra->idType][]=$extra->field;
    }
    self::$_extraRequiredFields=$result;
    setSessionValue('extraRequiredFieldsArray', $result);
    return $result;
  }

  private static function getExtraHiddenFieldsFullList() {
    if (self::$_extraHiddenFields!=null) {
      return self::$_extraHiddenFields;
    }
    $sessionList=getSessionValue('extraHiddenFieldsArray');
    if ($sessionList) {
      self::$_extraHiddenFields=$sessionList;
      return self::$_extraHiddenFields;
    }
    $extra=new ExtraHiddenField();
    $extraList=$extra->getSqlElementsFromCriteria(null); // Get all fields
    $result=array('Type'=>array(), 'Status'=>array(), 'Profile'=>array()); // Only scope for Type, Status, Profile
    foreach ($extraList as $extra) {
      $sp=pq_explode('#', $extra->scope);
      if (count($sp)!=2) return array();
      $scope=$sp[0];
      $class=$sp[1];
      if (!isset($result[$scope])) {
        errorLog("getExtraHiddenFieldsFullList() : some data has scope '$scope' different from Type, Status, Profile");
        return array();
      }
      if (!isset($result[$scope][$class])) $result[$scope][$class]=array();
      if (!isset($result[$scope][$class][$extra->idType])) $result[$scope][$class][$extra->idType]=array();
      $result[$scope][$class][$extra->idType][]=$extra->field;
    }
    self::$_extraHiddenFields=$result;
    setSessionValue('extraHiddenFieldsArray', $result);
    return $result;
  }

  public function getExtraReadonlyFields($newType="", $newStatus="", $newProfile="") {
    $class=get_class($this);
    // MTY - LEAVE SYSTEM
    if ($class=="Leave") {
      return array();
    }
    // MTY - LEAVE SYSTEM
    $testObj=$this;
    $testClass=$class;
    $typeFld='id' . $class . "Type";
    if (SqlElement::is_a($this, 'PlanningElement')) {
      if ($this->refType) {
        $testClass=$this->refType;
      } else {
        $testClass=pq_str_replace('PlanningElement', '', $class);
      }
      $testObj=new $testClass($this->refId, true);
    } else if ($class=='WorkElement') {
      if ($this->refType) {
        $testClass=$this->refType;
      } else {
        $testClass='Ticket';
      }
      $testObj=new $testClass($this->refId, true);
    }
    // $typeClass = $testClass . 'Type';
    $typeClass=SqlElement::getTypeClassName($testClass);
    // $typeFld = 'id' . $typeClass;
    $typeFld=SqlElement::getTypeName($testClass);
    // if ($class == 'TicketSimple')
    // $typeFld = 'idTicketType';
    $list=self::getExtraReadonlyFieldsFullList();
    $listType=array();
    $listStatus=array();
    $listProfile=array();
    if (property_exists($testObj, $typeFld) and $newType!='*') {
      $type=($newType)?$newType:$testObj->$typeFld;
      if (isset($list['Type']) and isset($list['Type'][$class]) and isset($list['Type'][$class][$type])) {
        $listType=$list['Type'][$class][$type];
      }
    }
    if (property_exists($testObj, 'idStatus') and $newStatus!='*') {
      $status=($newStatus)?$newStatus:$testObj->idStatus;
      if (!$status) {
        $status=$this->getFirstStatus($newType);
      }
      if (isset($list['Status']) and isset($list['Status'][$class]) and isset($list['Status'][$class][$status])) {
        $listStatus=$list['Status'][$class][$status];
      }
    }
    $listOther=array();
    if ($newProfile!='*') {
      if ($newProfile) {
        $profile=$newProfile;
      } else {
        $profile=getSessionUser()->getProfile($this);
      }
      if (isset($list['Profile']) and isset($list['Profile'][$class]) and isset($list['Profile'][$class][$profile])) {
        $listProfile=$list['Profile'][$class][$profile];
      }
      $changeValidatedData=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array(
          'idProfile'=>$profile,
          'scope'=>'changeValidatedData'));
      if ($changeValidatedData and ($changeValidatedData->rightAccess==2 or !$changeValidatedData->id)) {
        $listOther[]='validatedStartDate';
        $listOther[]='validatedEndDate';
        $listOther[]='validatedWork';
        $listOther[]='validatedDuration';
        $listOther[]='validatedCost';
        $listOther[]='expenseValidatedAmount';
      }
      $changePriorityProj=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array(
          'idProfile'=>$profile,
          'scope'=>'changePriorityProj'));
      if ($class=='Project' and $changePriorityProj and ($changePriorityProj->rightAccess==2 or !$changePriorityProj->id)) {
        $listOther[]='priority';
      }
      $changePriorityOther=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array(
          'idProfile'=>$profile,
          'scope'=>'changePriorityOther'));
      if ($class!='Project' and $changePriorityOther and ($changePriorityOther->rightAccess==2 or !$changePriorityOther->id)) {
        $listOther[]='priority';
      }
      $changeManualProgress=SqlElement::getSingleSqlElementFromCriteria('HabilitationOther', array(
          'idProfile'=>$profile,
          'scope'=>'changeManualProgress'));
      $pe=$class . 'PlanningElement';
      if (property_exists($class, $pe) and (!$this->$pe->isManualProgress or ($changeManualProgress->id and $changeManualProgress->rightAccess==2))) {
        $listOther[]='progress';
      }
    }
    if (property_exists($class, 'idMilestone') and Parameter::getGlobalParameter('milestoneFromVersion') and ((property_exists($class, 'idTargetProductVersion') and $this->idTargetProductVersion) or (property_exists($class, 'idProductVersion') and $this->idProductVersion))) {
      $pv=new ProductVersion((property_exists($class, 'idTargetProductVersion'))?$this->idTargetProductVersion:$this->idProductVersion);
      if ($pv->idMilestone) {
        $listOther[]='idMilestone';
      }
    }

    return array_unique(array_merge($listType, $listStatus, $listProfile, $listOther));
  }

  private static function getExtraReadonlyFieldsFullList() {
    if (self::$_extraReadonlyFields!=null) {
      return self::$_extraReadonlyFields;
    }
    $sessionList=getSessionValue('extraReadonlyFieldsArray');
    if ($sessionList) {
      self::$_extraReadonlyFields=$sessionList;
      return self::$_extraReadonlyFields;
    }
    $extra=new ExtraReadonlyField();
    $extraList=$extra->getSqlElementsFromCriteria(null); // Get all fields
    $result=array('Type'=>array(), 'Status'=>array(), 'Profile'=>array()); // Only scope for Type, Status, Profile
    foreach ($extraList as $extra) {
      $sp=pq_explode('#', $extra->scope);
      if (count($sp)!=2) return array();
      $scope=$sp[0];
      $class=$sp[1];
      if (!isset($result[$scope])) {
        errorLog("getExtraReadonlyFieldsFullList() : some data has scope '$scope' different from Type, Status, Profile");
        return array();
      }
      if (!isset($result[$scope][$class])) $result[$scope][$class]=array();
      if (!isset($result[$scope][$class][$extra->idType])) $result[$scope][$class][$extra->idType]=array();
      $result[$scope][$class][$extra->idType][]=$extra->field;
    }
    self::$_extraReadonlyFields=$result;
    setSessionValue('extraReadonlyFieldsArray', $result);
    return $result;
  }

  // ============================================================
  // Redefines standard class test function
  // to avoid error logging when not necessary
  // ============================================================
  public static function is_a($object, $class) {
    global $hideAutoloadError;
    $hideAutoloadError=true; // Avoid error message in autoload
    if (is_object($object)) {
      $result=($object instanceof $class);
    } else if (version_compare(PHP_VERSION, '5.3.9')>=0) {
      $result=@is_a($object, $class, true); // 3rd parameter "allow_string" is compatible only since V5.3.9
    } else {
      if (self::class_exists($object)) {
        $obj=new $object();
        $result=($obj instanceof $class);
      } else {
        $result=false;
      }
    }
    $hideAutoloadError=true;
    return $result;
  }

  public static function class_exists($item) {
    if ($item==null) return false;
    // PBER specific for imapMailbox as 2 clases exist on V11.4 for same class (loaded and used on Cron only)
    if ($item=='ImapMailbox') return true;
    if ($item=='ImapMailbox2') return false;
    global $hideAutoloadError;
    $hideAutoloadError=true; // Avoid error message in autoload
    $result=class_exists($item, true);
    $hideAutoloadError=false;
    return $result;
  }

  public static function is_subclass_of($className, $parentClass) {
    global $hideAutoloadError;
    $hideAutoloadError=true; // Avoid error message in autoload
    $result=is_subclass_of($className, $parentClass);
    $hideAutoloadError=false;
    return $result;
  }

  public static function getPrivacyClause($obj=null) {
    $isPrivate='isPrivate';
    $idUser='idUser';
    if ($obj) {
      if (!is_object($obj)) {
        $obj=new $obj();
      }
      $isPrivate=$obj->getDatabaseTableName() . '.' . $obj->getDatabaseColumnName('isPrivate');
      $idUser=$obj->getDatabaseTableName() . '.' . $obj->getDatabaseColumnName('idUser');
    }
    return "($isPrivate=0 or $idUser=" . Sql::fmtId(getSessionUser()->id) . ")";
  }

  // ADD BY Marc TABARY - 2017-02-24 - TRANSFORM OBJECT SQLELMENT LIST IN ARRAY KEY-NAME
  /**
   * =====================================================================================
   * Transform a collection of objects with class SqlElement to array type key - name
   * --------------------------------------------------------------------------------------
   *
   * @param
   *          sqlElement Objects - $objSqlElt : The objects of class SqlElement to transform
   * @return array key-name
   */
  public static function transformObjSqlElementInArrayKeyName($objSqlElt) {
    if ($objSqlElt==null) {
      return array();
    }
    $theobjSqlElt=$objSqlElt[0];
    $ancestor_class=get_parent_class($theobjSqlElt);
    while ($ancestor_class!=false and $ancestor_class!='SqlElement') {
      $ancestor_class=get_parent_class($ancestor_class);
    }
    if ($ancestor_class!='SqlElement') {
      return array();
    }

    foreach ($objSqlElt as $theObj) {
      $array[$theObj->id]=$theObj->name;
    }
    return $array;
  }

  // END ADD BY Marc TABARY - 2017-02-24 - TRANSFORM OBJECT SQLELMENT LIST IN ARRAY KEY-NAME
  protected function updateMessage($message, $nodataMsg, $status='INVALID') {
    $result=new ResultHandler(ResultHandler::TYPE_UPDATE, $status, $message, null, $nodataMsg=null, $this->id);
    return $result;
  }

  protected function insertMessage($message, $status='OK') {
    $result=new ResultHandler(ResultHandler::TYPE_INSERT, $status, $message, null, null, $this->id);
    return $result;
  }

  protected function copyMessage($message, $newId, $status='OK') {
    $result=new ResultHandler(ResultHandler::TYPE_COPY, $status, $message, null, null, $newId);
    return $result;
  }

  protected function deleteMessage($message, $nodataMsg, $status='INVALID') {
    $result=new ResultHandler(ResultHandler::TYPE_DELETE, $status, $message, null, $nodataMsg, $this->id);
    return $result;
  }

  protected function controlMessage($control, $status='INVALID') {
    $result=new ResultHandler(ResultHandler::TYPE_CONTROL, $status, null, $control, null, $this->id);
    return $result;
  }

  // ADD qCazelles - Filter by status
  public function getExistingStatus() {
    if (!property_exists($this, 'idStatus')) return array();
    $clsName=get_class($this);
    $arraySessionStatus=array();
    foreach (getAllSessionValues() as $codeSess=>$valSess) {
      if ($valSess=='true' and pq_substr($codeSess, 0, 10)=='showStatus' and pq_substr($codeSess, pq_strlen($clsName)*(-1))==$clsName) {
        $idx=pq_str_replace(array('showStatus', $clsName), array('', ''), $codeSess);
        $arraySessionStatus[$idx]=$idx;
      }
    }
    $where='id in (select distinct idStatus from ' . $this->getDatabaseTableName() . ')';
    if (count($arraySessionStatus)>0) {
      $where.=' or id in ' . transformListIntoInClause($arraySessionStatus);
    }
    $status=new Status();
    $list=$status->getSqlElementsFromCriteria(null, null, $where, 'sortOrder asc');
    return $list;
  }

  // END ADD qCazelles - Filter by status
  public function getExistingTags() {
    if (!property_exists($this, 'tags')) return array();
    $clsName=get_class($this);
    $arraySessionTags=array();
    foreach (getAllSessionValues() as $codeSess=>$valSess) {
      if ($valSess=='true' and pq_substr($codeSess, 0, 10)=='showTags' and pq_substr($codeSess, pq_strlen($clsName)*(-1))==$clsName) {
        $idx=pq_str_replace(array('showTags', $clsName), array('', ''), $codeSess);
        $arraySessionTags[$idx]=$idx;
      }
    }
    $where="refType = '" . Tag::getRefType($clsName) . "'";
    if (count($arraySessionTags)>0) {
      $where.=' or id in ' . transformListIntoInClause($arraySessionTags);
    }
    if (Parameter::getGlobalParameter('listTagsPerProject')=="YES") {
      $where.=" AND idProject in " . getVisibleProjectsList();
    }
    $tag=new Tag();
    $list=SqlList::getListWithCrit('Tag', $where);
    $listUnique=array_unique($list);
    $list=array();
    foreach ($listUnique as $id=>$name) {
      $list[]=(object)array('id'=>$id, 'name'=>$name);
    }
    return $list;
  }

  public static function toArrayList($list, $parent=null, $outputHtml=false) {
    $result=array();
    foreach ($list as $obj) {
      $result[]=$obj->toArrayFields($parent, $outputHtml);
    }
    return $result;
  }

  public function toArrayFields($parent=null, $outputHtml=false) {
    $result=array();
    foreach ($this as $fld=>$value) {
      if (is_object($value)) {
        if (SqlElement::is_a($value, 'SqlElement')) {
          $sub=$value->toArrayFields($this, $outputHtml);
          $result[pq_strtolower($fld)]=array($sub);
        }
        continue;
      }
      if (is_array($value)) {
        $pos=strrpos($fld, '_');
        $subClass=pq_substr($fld, 1);
        $pos=pq_strpos($subClass, '_');
        if ($pos) {
          $subClass=pq_substr($fld, 0, $pos);
        }
        if (SqlElement::class_exists($subClass)) {
          if (pq_strtolower($subClass)=="billline") $value=array_reverse($value);
          $sub=SqlElement::toArrayList($value, $this, $outputHtml);
          $result[pq_strtolower($subClass)]=$sub;
          if ($subClass=='Link') {
            foreach (SqlList::getListNotTranslated('Linkable') as $linkable) {
              $result["link_$linkable"]=array();
            }
            foreach ($sub as $link) {
              $lnkClass=$link['refType'];
              if (!isset($result["link_$lnkClass"])) $result["link_$lnkClass"]=array();
              $result["link_$lnkClass"][]=$link;
            }
          }
        }
        continue;
      }
      if (pq_substr($fld, 0, 1)=='_') continue;
      $result[$fld]=$value;
      $dataType=$this->getDataType($fld);
      $dataLength=$this->getDataLength($fld);
      if ($dataLength>4000) { // Big text html formatted : must be transformed into plain text
        $text=new Html2Text($value);
        $result[$fld . 'Text']=$text->getText();
        $result[$fld]=$value;
      } else if (isForeignKey($fld, $this)) { // idXxx : also add nameXxx
        $class=pq_substr(foreignKeyWithoutAlias($fld), 2);
        if (pq_strpos($fld, '__')!==false&&pq_substr($fld, 0, 2)!=='id') {
          $fldName='label' . ucfirst($fld);
        } else {
          $fldName='name' . pq_substr($fld, 2);
        }
        if ($class=='Resource' or $class=='User' or $class=='Contact') {
          $result[$fldName]=SqlList::getNameFromId('Affectable', $value);
        } else if (SqlElement::class_exists($class) and property_exists($class, 'name')) {
          $result[$fldName]=SqlList::getNameFromId($class, $value);
        }
        if ($fld==SqlElement::getTypeName(get_class($this))) {
          $result['idType']=$value;
          $result['nameType']=$result['name' . $class];
        }
      } else if ($dataType=='date') {
        $result[$fld]=htmlFormatDate($value);
      } else if ($dataType=='time') {
        $result[$fld]=htmlFormatTime($value);
      } else if ($dataType=='datetime') {
        $result[$fld]=htmlFormatDateTime($value);
      } else if (self::isAmount($fld)) {
        if (self::isLocal($fld)) $tmpVal=($this->hasCurrency())?htmlDisplayLocalCurrency((get_class($this)=='Project'?$this->id:$this->idProject), null, $value):'';
        else $tmpVal=htmlDisplayCurrency($value);
        if (!$outputHtml) $tmpVal=pq_str_replace('&nbsp;', ' ', $tmpVal);
        $result[$fld]=$tmpVal;
      } else if ($dataType=="numeric" or $dataType=="decimal") {
        $tmpVal=htmlDisplayNumericWithoutTrailingZeros($value);
        if (!$outputHtml) $tmpVal=pq_str_replace('&nbsp;', ' ', $tmpVal);
        $result[$fld]=$tmpVal;
      } else if ($outputHtml) {
        $result[$fld]=htmlEncode($value, 'html');
      }
    }
    if (property_exists($this, 'refType') and property_exists($this, 'refId') and !property_exists($this, 'refName')) {
      $result['refName']=self::getRefName($this->refType, $this->refId);
      $result['refTypeName']=i18n($this->refType);
    }
    if (property_exists($this, 'originType') and property_exists($this, 'originId')) {
      $result['originName']=self::getRefName($this->originType, $this->originId);
      $result['originTypeName']=i18n($this->originType);
      $result['originExternalReference']=($this->originType and property_exists($this->originType, 'externalReference'))?self::getRefField($this->originType, $this->originId, 'externalReference'):'';
      $result['originEndDate']='';
      if ($this->originType and property_exists($this->originType, 'validatedEndDate')) {
        $validatedEnd=self::getRefField($this->originType, $this->originId, 'validatedEndDate');
        if ($validatedEnd) $result['originEndDate']=htmlFormatDate($validatedEnd);
        else {
          $initialEnd=self::getRefField($this->originType, $this->originId, '$initialEnd');
          if ($initialEnd) $result['originEndDate']=htmlFormatDate($initialEnd);
        }
      }
    }
    if (get_class($this)=='Attachment') {
      if ($this->link) $this->fileName=$this->link;
    }
    if (property_exists($this, 'ref1Type') and property_exists($this, 'ref1Id') and property_exists($this, 'ref2Type') and property_exists($this, 'ref2Id')) {
      $result['ref1Name']=self::getRefName($this->ref1Type, $this->ref1Id);
      $result['ref2Name']=self::getRefName($this->ref2Type, $this->ref2Id);
      if ($parent and get_class($parent)==$this->ref1Type and $parent->id==$this->ref1Id and !property_exists($this, 'refType') and !property_exists($this, 'refName')) {
        $result['refType']=$this->ref2Type;
        $result['refId']=$this->ref2Id;
        $result['refName']=$result['ref2Name'];
        $result['refTypeName']=i18n($this->ref2Type);
        $result['refStatus']=self::getRefStatus($this->ref2Type, $this->ref2Id);
        $result['refResponsible']=self::getRefResponsible($this->ref2Type, $this->ref2Id);
        $result['refInitialDueDate']=self::getRefInitialDueDate($this->ref2Type, $this->ref2Id);
        $result['refActualDueDate']=self::getRefActualDueDate($this->ref2Type, $this->ref2Id);
        $result['refDate']=self::getRefDate($this->ref2Type, $this->ref2Id);
        $result['refDescription']=self::getRefDescription($this->ref2Type, $this->ref2Id);
        if (property_exists($this->ref2Type, 'contactFunction')) $result['contactFunction']=SqlList::getFieldFromId($this->ref2Type, $this->ref2Id, 'contactFunction');
        if (property_exists($this->ref2Type, 'email')) $result['email']=SqlList::getFieldFromId($this->ref2Type, $this->ref2Id, 'email');
        if (property_exists($this->ref2Type, 'phone')) $result['phone']=SqlList::getFieldFromId($this->ref2Type, $this->ref2Id, 'phone');
      } else {
        $result['refType']=$this->ref1Type;
        $result['refId']=$this->ref1Id;
        $result['refName']=$result['ref1Name'];
        $result['refTypeName']=i18n($this->ref1Type);
        $result['refStatus']=self::getRefStatus($this->ref1Type, $this->ref1Id);
        $result['refResponsible']=self::getRefResponsible($this->ref1Type, $this->ref1Id);
        $result['refInitialDueDate']=self::getRefInitialDueDate($this->ref1Type, $this->ref1Id);
        $result['refActualDueDate']=self::getRefActualDueDate($this->ref1Type, $this->ref1Id);
        $result['refDate']=self::getRefDate($this->ref1Type, $this->ref1Id);
        $result['refDescription']=self::getRefDescription($this->ref1Type, $this->ref1Id);
        if ($this->ref1Type and property_exists($this->ref1Type, 'contactFunction')) $result['contactFunction']=SqlList::getFieldFromId($this->ref1Type, $this->ref1Id, 'contactFunction');
        if ($this->ref1Type and property_exists($this->ref1Type, 'email')) $result['email']=SqlList::getFieldFromId($this->ref1Type, $this->ref1Id, 'email');
        if ($this->ref1Type and property_exists($this->ref1Type, 'phone')) $result['phone']=SqlList::getFieldFromId($this->ref1Type, $this->ref1Id, 'phone');
      }
    }
    if (get_class($this)=='Project' and !$parent) {
      $aff=new Affectation();
      $affList=$aff->getSqlElementsFromCriteria(array('idProject'=>$this->id, 'idle'=>'0'));
      $sub=SqlElement::toArrayList($affList, $this, $outputHtml);
      $result['affectation']=$sub;
    }
    return $result;
  }

  private static $_lastRefObject=null;

  public static function getRefName($refType, $refId) {
    return self::getRefField($refType, $refId, 'name');
  }

  public static function getRefStatus($refType, $refId) {
    $idStatus=self::getRefField($refType, $refId, 'idStatus');
    return ($idStatus)?SqlList::getNameFromId('Status', $idStatus):'';
  }

  public static function getRefDescription($refType, $refId) {
    $desc=self::getRefField($refType, $refId, 'description');
    $text=new Html2Text($desc);
    return $text->getText();
  }

  public static function getRefResponsible($refType, $refId) {
    $idResource=self::getRefField($refType, $refId, 'idResource');
    return ($idResource)?SqlList::getNameFromId('Affectable', $idResource):'';
  }

  public static function getRefInitialDueDate($refType, $refId) {
    $refObj=self::getRefObj($refType, $refId);
    if (property_exists($refObj, 'initialDueDate')) {
      return htmlFormatDate($refObj->initialDueDate);
    } else if (property_exists($refObj, 'initialDueDateTime')) {
      return htmlFormatDate($refObj->initialDueDateTime, true);
    } else if (property_exists($refObj, 'initialEndDate')) {
      return htmlFormatDate($refObj->initialEndDate, true);
    } else {
      return '';
    }
  }

  public static function getRefActualDueDate($refType, $refId) {
    $refObj=self::getRefObj($refType, $refId);
    if (property_exists($refObj, 'actualDueDate')) {
      return htmlFormatDate($refObj->actualDueDate);
    } else if (property_exists($refObj, 'actualDueDateTime')) {
      return htmlFormatDate($refObj->actualDueDateTime, true);
    } else if (property_exists($refObj, 'actualEndDate')) {
      return htmlFormatDate($refObj->actualEndDate, true);
    } else {
      return '';
    }
  }

  public static function getRefDate($refType, $refId) {
    $initial=self::getRefActualDueDate($refType, $refId);
    if ($initial) return $initial;
    $actual=self::getRefInitialDueDate($refType, $refId);
    if ($actual) return $actual;
    $decision=self::getRefField($refType, $refId, 'decisionDate');
    if ($decision) return htmlFormatDate($decision);
    return '';
  }

  public static function getRefObj($refType, $refId) {
    if ($refType and $refId and SqlElement::class_exists($refType)) {
      if (self::$_lastRefObject and is_object(self::$_lastRefObject) and get_class(self::$_lastRefObject)==$refType and self::$_lastRefObject->id==$refId) {
        $refObj=self::$_lastRefObject;
      } else {
        $refObj=new $refType($refId);
        self::$_lastRefObject=$refObj;
      }
    } else {
      if ($refType and !SqlElement::class_exists($refType)) {
        traceLog("SqlElement::getRefObj() : '$refType' does not reference a valid object class");
        // debugPrintTraceStack();
      }
      $refObj=new stdClass();
    }
    return $refObj;
  }

  public static function getRefField($refType, $refId, $field) {
    if ($field=='name' and ($refType=='Resource' or $refType=='User' or $refType=='Contact')) $refType='Affectable';
    if (!$refType or !$field) return '';
    $refObj=self::getRefObj($refType, $refId);
    if (property_exists($refObj, $field)) {
      return $refObj->$field;
    } else {
      return '';
    }
  }

  // public function setAttributes() {
  // DO NOT SET GLOBAL DEFINITION AS SIGNATURE DEPENDS ON ITEM
  // }
  public function getFirstStatus($type) {
    // Up to V6.5, first status is always first in the list, whatever the workflow
    // $stList=SqlList::getList('Status');
    $stList=SqlList::getStatusList(get_class($this));
    $first=reset($stList);
    $status=key($stList); // first status always first in the list
    return $status;
  }

  public static function mergeAttributesArrays($selfArray, $parentArray) {
    foreach ($parentArray as $key=>$val) {
      if (!isset($selfArray[$key])) {
        $selfArray[$key]=$val;
      } else {
        $selfArray[$key].=',' . $val;
      }
    }
    // return self::$_fieldsAttributes=array_merge_preserve_keys($selfArray,$parentArray);
    return $selfArray;
  }

  public static function traceFields($obj, $fields) {
    if (!is_array($fields)) $fields=array($fields);
    $msg="=> " . get_class($obj) . ' #' . $obj->id;
    foreach ($fields as $fld) {
      $msg.=", $fld=";
      if (property_exists($obj, $fld)) {
        $msg.=$obj->$fld;
      } else {
        $msg.='#not a field#';
      }
    }
    debugTraceLog($msg);
  }

  // florent #4442
  public function searchLastAttachmentMailable() {
    $allAttach=searchAllAttachmentMailable(get_class($this), $this->id);
    $lstAttach=$allAttach[0];
    if (!empty($lstAttach)) $att=$lstAttach[0];
    if (isset($att)) {
      if ($att->idPrivacy==1) {
        return $name=$att->id . '_file/' . (($att->fileSize!='')?$att->fileSize:0);
      }
    } else {
      return;
    }
  }

  public function searchAllAttachmentsMailable($maxSizeAttachment) {
    $allAttach=searchAllAttachmentMailable(get_class($this), $this->id);
    $lstAttach=$allAttach[0];
    $attachments=array();
    $size=0;
    $c=0;
    $message='Ok';
    foreach ($lstAttach as $att) {
      $c++;
      if ($att->idPrivacy==1) {
        $size+=($att->fileSize!='')?$att->fileSize:0;
        if ($size>$maxSizeAttachment) {
          break;
        } else {
          $attachments[]=array($att->id, 'file');
        }
      } else {
        continue;
      }
    }
    if (count($lstAttach)!=$c) {
      $message='Fail';
    }
    return array('attachments'=>$attachments, 'result'=>$message);
  }

  //
  public function addFirstErrorField($obj, $col, &$result, $layout, &$exist) {
    $sectionPosition=self::setSectionPosition();
    $exist=true;
    $isPlan=false;
    $isWork=false;
    $asObje="";
    $objectClass=get_class($obj);
    if (pq_strpos($objectClass, 'PlanningElement')) {
      $asObje=$objectClass;
      $isPlan=true;
    } else if (pq_strpos($objectClass, 'WorkElement')) {
      $asObje=$objectClass;
      $isWork=true;
    }
    if ($asObje!="") {
      if ($isPlan) {
        $objCl=pq_trim(pq_str_replace("PlanningElement", "", $objectClass));
      } else {
        $objCl=pq_trim(pq_str_replace("PlanningElement", "", WorkElement));
      }
      $obj=new $objCl();
    }
    if ($layout=='tab') {
      $section='';
      foreach ($obj->getFieldsList() as $id) {
        if (pq_substr($id, 0, 5)=='_sec_') {
          $section=lcfirst(pq_substr($id, 5));
        }
        if ($id==$col) {
          break;
        }
        if ($asObje!="" and $id==$objectClass) {
          $asCol=false;
          $val=$obj->$id;
          foreach ($val as $elId=>$elVal) {
            if ($elId==$col) {
              $asCol=true;
              break;
            }
          }
          if ($asCol==true) break;
        }
      }
      $position='detail';
      if (isset($sectionPosition[pq_strtolower($section)]['99'])) {
        $position=$sectionPosition[pq_strtolower($section)]['99'];
      }
      $tab=$position;
      $field='<input id="firstFieldRequired" value="' . $col . '" hidden />';
      $tab='<input id="firstTabdRequired" value="' . $tab . '" hidden />';
      $isSpecificObj='<input id="isSepcificObj" value="' . $asObje . '" hidden />';
      $result=$result . $field . $tab . $isSpecificObj;
    } else {
      $field='<input id="firstFieldRequired" value="' . $col . '" hidden />';
      $isSpecificObj='<input id="isSepcificObj" value="' . $asObje . '" hidden />';
      $result=$result . $field . $isSpecificObj;
    }
  }

  public static function setSectionPosition() {
    $sectionPosition=array(
        'accessright'=>array('2'=>'extra', '3'=>'history', '99'=>'description'),
        'assignment'=>array('2'=>'left', '3'=>'extra', '99'=>'progress'),
        'affectations'=>array('2'=>'right', '3'=>'right', '99'=>'allocation'),
        'affectationresourceteamresource'=>array('2'=>'right', '3'=>'right', '99'=>'allocation'),
        'affectationsresourceteam'=>array('2'=>'right', '3'=>'right', '99'=>'resources'),
        'answer'=>array('2'=>'right', '3'=>'right', '99'=>'treatment'),
        'approver'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'approverdecision'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'attachment'=>array('2'=>'bottom', '3'=>'extra', '99'=>'fichier'),
        'attendees'=>array('2'=>'right', '3'=>'extra', '99'=>'progress'),
        'billline'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'billlineterm'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'billslist'=>array('2'=>'bottom', '3'=>'extra', '99'=>'financial'),
        'budgetsynthesis'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'calendar'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'checklistdefinitionline'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'description'),
        'checklist'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'checklist'),
        'commandslist'=>array('2'=>'bottom', '3'=>'extra', '99'=>'financial'),
        'componentcomposition'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'componentstructure'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'componentversions'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'componentversioncomposition'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'componentversionstructure'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'context'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'contextlocalization'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'context'),
        'contacts'=>array('2'=>'right', '3'=>'right', '99'=>'detail'),
        'delivery'=>array('2'=>'bottom', '3'=>'extra', '99'=>'link'),
        'description'=>array('2'=>'left', '3'=>'left', '99'=>'description'),
        'description_tokenDef'=>array('2'=>'left', '3'=>'left', '99'=>'detail'),
        'evaluation'=>array('2'=>'left', '3'=>'extra', '99'=>'progress'),
        'evaluationcriteria'=>array('2'=>'right', '3'=>'extra', '99'=>'progress'),
        'eventprospect'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'treatment'),
        'expensedetail'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'helpallowedwords'=>array('3'=>'bottom', '3'=>'extra', '99'=>'detail'),
        'helpallowedreceivers'=>array('3'=>'bottom', '3'=>'extra', '99'=>'detail'),
        'hierarchicorganizationprojects'=>array('2'=>'bottom', '3'=>'extra', '99'=>'projects'),
        'history'=>array('2'=>'history', '3'=>'history', '99'=>'history'),
        'iban'=>array('2'=>'right', '3'=>'extra', '99'=>'detail'),
        'internalalert'=>array('2'=>'right', '3'=>'extra', '99'=>'detail'),
        'joblist'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'checklist'),
        'jobdefinition'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'description'),
        'link'=>array('2'=>'bottom', '3'=>'extra', '99'=>'link'),
        'link_activity'=>array('2'=>'left', '3'=>'extra', '99'=>'link'),
        'link_deliverable'=>array('2'=>'left', '3'=>'extra', '99'=>'link'),
        'link_prospect'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'link'),
        'link_requirement'=>array('2'=>'bottom', '3'=>'extra', '99'=>'coverage'),
        'link_testcase'=>array('2'=>'bottom', '3'=>'extra', '99'=>'coverage'),
        'linkedlocalizationitems'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'localizationItems'),
        'listtypeusingworkflow'=>array('2'=>'right', '3'=>'extra', '99'=>'link'),
        'loyaltyevent'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'treatment'),
        'lock'=>array('2'=>'left', '3'=>'left', '99'=>'description'),
        'mailtext'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'members'=>array('2'=>'right', '3'=>'right', '99'=>'resources'),
        'miscellaneous'=>array('2'=>'right', '3'=>'extra', '99'=>'detail'),
        'note'=>array('2'=>'bottom', '3'=>'extra', '99'=>'note'),
        'notificationtitle'=>array('2'=>'left', '3'=>'left', '99'=>'description'),
        'notificationrule'=>array('2'=>'left', '3'=>'left', '99'=>'treatment'),
        'notificationcontent'=>array('2'=>'left', '3'=>'right', '99'=>'description'),
        'notification'=>array('3'=>'bottom', '3'=>'extra', '99'=>'description'),
        'pokeritem'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'pokervote'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'treatment'),
        'predecessor'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'dependency'),
        'price'=>array('2'=>'right', '3'=>'right', '99'=>'treatment'),
        'projectsofobject'=>array('2'=>'bottom', '3'=>'extra', '99'=>'dependency'),
        'progress'=>array('2'=>'right', '3'=>'extra', '99'=>'description', '99'=>'progress'),
        'progress_left'=>array('2'=>'left', '3'=>'extra', '99'=>'progress'),
        'progress_center'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'productprojectprojects'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'abacus'=>array('2'=>'right', '3'=>'right', '99'=>'abacus'),
        'productprojectproducts'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'productcomponent'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'productcomponent_right'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'productcomposition'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'productbusinessfeatures'=>array('2'=>'right', '3'=>'right', '99'=>'detail'),
        'productversions'=>array('2'=>'left', '3'=>'extra', '99'=>'configuration'),
        'productversioncomposition'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'productversioncompatibility'=>array('2'=>'left', '3'=>'right', '99'=>'configuration'),
        'projectdailyhours'=>array('2'=>'left', '3'=>'right', '99'=>'treatment'),
        'proposal'=>array('2'=>'right', '3'=>'right', '99'=>'proposal'),
        'providerterm'=>array('2'=>'right', '3'=>'extra', '99'=>'detail'),
        'prospectestimatelist'=>array('2'=>'bottom', '3'=>'extra', '99'=>'financial'),
        'quotationslist'=>array('2'=>'bottom', '3'=>'extra', '99'=>'financial'),
        'receivers'=>array('2'=>'bottom', '3'=>'extra', '99'=>'treatment'),
        'resourcesofobject'=>array('2'=>'bottom', '3'=>'extra', '99'=>'resources'),
        'resourcecost'=>array('2'=>'right', '3'=>'extra', '99'=>'detail'),
        'situation'=>array('2'=>'right', '3'=>'extra', '99'=>'detail'),
        'situationexpense'=>array('2'=>'left', '3'=>'right', '99'=>'detail'),
        'situationincome'=>array('2'=>'right', '3'=>'right', '99'=>'detail'),
        'subprojects'=>array('2'=>'right', '3'=>'right', '99'=>'dependency'),
        'subproducts'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'subbudgets'=>array('2'=>'right', '3'=>'extra', '99'=>'dependency'),
        'submissions'=>array('2'=>'right', '3'=>'extra', '99'=>'progress'),
        'subscriptioncontact'=>array('2'=>'bottom', '3'=>'extra', '99'=>'link'),
        'synthesis'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'successor'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'dependency'),
        'target'=>array('2'=>'bottom', '3'=>'extra', '99'=>'treatment'),
        'treatment'=>array('2'=>'right', '3'=>'right', '99'=>'treatment'),
        'treatment_right'=>array('2'=>'right', '3'=>'extra', '99'=>'treatment'),
        'treatmen_tokenDeft'=>array('2'=>'right', '3'=>'right', '99'=>'detail'),
        'ticket'=>array('2'=>'bottom', '3'=>'extra', '99'=>'link'),
        'ticketscontact'=>array('2'=>'bottom', '3'=>'extra', '99'=>'link'),
        'ticketsclient'=>array('2'=>'bottom', '3'=>'extra', '99'=>'link'),
        'tickethistory'=>array('2'=>'right', '3'=>'extra', '99'=>'History'),
        'tenders'=>array('2'=>'bottom', '3'=>'extra', '99'=>'detail'),
        'testcaserun'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'coverage'),
        'testcaserunsummary'=>array('2'=>'left', '3'=>'extra', '99'=>'coverage'),
        'testcasesummary'=>array('2'=>'right', '3'=>'extra', '99'=>'coverage'),
        'totalfinancialsynthesis'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'validation'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'valuealertoverwarningoverokunder'=>array('2'=>'right', '3'=>'right', '99'=>'progress'),
        'version'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'versionprojectversions'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'versionprojectprojects'=>array('2'=>'right', '3'=>'right', '99'=>'configuration'),
        'void'=>array('2'=>'right', '3'=>'right', '99'=>'descrpition'),
        'workflowdiagram'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'workflowstatus'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'detail'),
        'worktokenclientcontract'=>array('2'=>'bottom', '3'=>'bottom', '99'=>'progress'));
    return $sectionPosition;
  }

  public function getObjectTypeName() {
    $class=get_class($this);
    return self::getTypeName($class);
  }

  public static function getTypeName($class) {
    $typeFld='id' . pq_str_replace('PlanningElement', '', $class) . 'Type';
    if ($class=='PeriodicMeeting') $typeFld='idMeetingType';
    else if ($class=='TicketSimple') $typeFld='idTicketType';
    else if ($class=='EmployeeLeaveEarned') $typeFld='idLeaveType';
    return $typeFld;
  }

  public static function getTypeClassName($class) {
    $typeName=self::getTypeName($class);
    return pq_substr($typeName, 2);
  }

  public static function isAmount($field) {
    if (pq_substr($field, -4)=='Cost' or pq_substr($field, -6)=='Amount') return true;
    if (pq_substr($field, -9)=='CostLocal' or pq_substr($field, -11)=='AmountLocal') return true;
    if ($field=='amount' or $field=='price' or $field=='revenue' or $field=='commandSum' or $field=='billSum') return true;
    if ($field=='amountLocal' or $field=='priceLocal' or $field=='revenueLocal' or $field=='commandSumLocal' or $field=='billSumLocal') return true;
    return false;
  }

  public static function isWork($field) {
    if (pq_substr($field, -4)=='Work' or pq_substr($field, -9)=='WorkLocal') return true;
    return false;
  }

  public static function isDate($field) {
    if (pq_substr($field, -4)=='Date' or pq_substr($field, -9)=='DateLocal') return true;
    return false;
  }

  public static function isAmountOrWork($field) {
    if (self::isAmount($field) or self::isWork($field)) return true;
    return false;
  }

  public static function isPct($field) {
    if (pq_substr($field, -3)=='Pct' or pq_strtolower(pq_substr($field, -8))=='progress' or pq_substr($field, -4)=='Rate' or pq_substr($field, -8)=='PctLocal' or pq_substr($field, -9)=='RateLocal') return true;
    return false;
  }

  public static function isLocal($field) {
    if (pq_substr($field, -5)=='Local') return true;
    return false;
  }

  public function hasCurrency() {
    if (!property_exists($this, 'idProject')) return false;
    else if (get_class($this)=='Project') return Project::hasProjectCurrency($this->id);
    else return Project::hasProjectCurrency($this->idProject);
  }

  public function showGlobalCurrency() {
    if (Parameter::getGlobalParameter("multiCurrency")!='YES') return true;
    else if (!$this->hasCurrency()) return true;
    else if (Parameter::getUserParameter("multiCurrencyShowGlobal")!='YES') return false;
    else return true;
  }

  public function getCurrencyPosition($field) {
    global $currencyPosition, $currencyPositionGlobal, $currencyPositionLocal;
    if (self::isLocal($field)) {
      if ($currencyPositionLocal) return $currencyPositionLocal;
      else if (get_class($this)=='Project') return Project::getProjectCurrencyPosition($this->id);
      else if (property_exists($this, 'idProject')) return Project::getProjectCurrencyPosition($this->idProject);
      else return $this->getCurrencyPosition('global');
    } else {
      if ($currencyPositionGlobal) return $currencyPositionGlobal;
      else if ($currencyPosition) return $currencyPosition;
      else return Parameter::getGlobalParameter('currencyPosition');
    }
  }

  public function getCurrency($field) {
    global $currency, $currencyGlobal, $currencyLocal;
    if (self::isLocal($field)) {
      if ($currencyLocal) return $currencyLocal;
      else if (get_class($this)=='Project') return Project::getProjectCurrency($this->id);
      else if (property_exists($this, 'idProject')) return Project::getProjectCurrency($this->idProject);
      else return $this->getCurrency('global');
    } else {
      if ($currencyGlobal) return $currencyGlobal;
      else if ($currency) return $currency;
      else return Parameter::getGlobalParameter('currency');
    }
  }

  public function getLocalToGlobalConversionRate($idProject=null) {
    if ($idProject==null) {
      if (get_class($this)=='Project') $idProject=$this->id;
      else if (property_exists($this, 'idProject')) $idProject=$this->idProject;
    }
    if ($idProject==null) return 1;
    else return Project::getProjectConversionRate($idProject);
  }

  public function getGlobalToLocalConversionRate($idProject=null) {
    if ($idProject==null) {
      if (get_class($this)=='Project') $idProject=$this->id;
      else if (property_exists($this, 'idProject')) $idProject=$this->idProject;
    }
    if ($idProject==null) return 1;
    else return round(1/Project::getProjectConversionRate($idProject), 5);
  }

  public function calculateGlobalFromLocal($val, $idProject=null) {
    if ($val==null) return $val;
    $conv=$this->getLocalToGlobalConversionRate($idProject);
    if ($conv) return round($val*$conv, 2);
    else return $val;
  }

  public function calculateLocalFromGlobal($val, $idProject=null) {
    if ($val==null) return $val;
    $conv=$this->getGlobalToLocalConversionRate($idProject);
    if ($conv) return round($val*$conv, 2);
    else return $val;
  }

  public function getLocalToGlobalUpdateScript($localField, $globalField=null) {
    if (!$this->hasCurrency()) return '';
    if (!$globalField) $globalField=pq_substr($localField, 0, -5);
    $conversion=$this->getLocalToGlobalConversionRate();
    if (!$conversion) return '';
    $res='';
    $res.="<script type='dojo/connect' event='onChange'>";
    $res.="  local=dijit.byId('$localField').get('value');";
    $res.="  var conversion=$conversion;";
    $res.="  var globalValue=calculateAmountFromConvertion(local,conversion,'$globalField');";
    $res.="</script>";
    return $res;
  }

}

?>
