<?php
require_once '../tool/projeqtor.php';
require_once '../tool/projeqtor_string.php';

if(Parameter::getGlobalParameter('subscriptionCodeStatus') != 'OK'){
  echo '../tool/subscriptionRequired.php'.Security::addTokenIndexToUrl('?');
  exit;
}
$userLink=array();
$userLink['Welcome']='index.html';
$userLink['Absence']='RealWorkAllocation.html#absence';
$userLink['Acceptance']='Incomes.html#acceptance';
$userLink['AccessProfile']='AccessRights.html#project-dependant';
$userLink['AccessProfileNoProject']='AccessRights.html#not-project-dependant';
$userLink['AccessRight']='AccessRights.html#access-mode-to-data-project-dependant';
$userLink['AccessRightNoProject']='AccessRights.html#access-mode-to-data-not-project-dependant';
$userLink['Action']='RiskIssueManagement.html#action';
$userLink['ActionType']='ListsOfTypes.html#action-type';
$userLink['Activity']='PlanningElements.html#activity';
$userLink['ActivityPrice']='Incomes.html#activity-price';
$userLink['ActivityStream']='TransverseFeatures.html#activity-stream';
$userLink['ActivityType']='ListsOfTypes.html#activity-type';
$userLink['Administration']='Administration.html#administration-console';
$userLink['Affectation']='Concept.html#allocation-to-project';
$userLink['Alert']='Tools.html#alerts';
$userLink['Assets']='AssetManagement.html';
$userLink['AssetType']='AssetManagement.html#asset-types';
$userLink['AssetCategory']='AssetManagement.html#asset-category';
$userLink['Assignement']='Concept.html#assignment';
$userLink['Assumption']='Steering.html#project-analysis';
$userLink['Audit']='Tools.html#audit-connections';
$userLink['AutoSendReport']='Report.html#sending-report';

$userLink['Bill']='Incomes.html#client-bill';
$userLink['BillType']='ListsOfTypes.html#bill-type';
$userLink['Brand']='AssetManagement.html#brands';
$userLink['Budget']='Expenses.html#budget';

$userLink['CalendarDefinition']='Resource.html#calendars';
$userLink['CallForTender']='Expenses.html#call-for-tenders';
$userLink['Catalog']='Incomes.html#catalog';
$userLink['ChangeRequest']='Steering.html#change-request';
$userLink['ChecklistDefinition']='ControlAutomation.html#checklist-definition';
$userLink['Client']='Customer.html#customer';
$userLink['ClientContract']='Incomes.html#client-contract';
$userLink['ClientType']='ListsOfTypes.html#customer-type';
$userLink['Command']='Incomes.html#client-orders';
$userLink['CommandType']='ListsOfTypes.html#order-type';
$userLink['Component']='ConfigurationManagement.html#component';
$userLink['ComponentVersion']='ConfigurationManagement.html#component-version';
$userLink['ConsolidationValidation']='RealWorkAllocation.html#monthly-consolidation';
$userLink['Constraint']='Steering.html#project-analysis';
$userLink['Contact']='Customer.html#contact';
$userLink['Context']='Concept.html#context';
$userLink['ContextType']='ListsOfTypes.html#context-type';
$userLink['ContractGantt']='Financial.html#gantt-contract';
$userLink['Criticality']='ListsOfValues.html#criticality';
$userLink['CriticalResources']='Gantt.html#critical-resource';

$userLink['dashboardEmployeeManager']='HumanResources.html#leaves-dashboard';
$userLink['DataCloning']='Tools.html#cloned-environment';
$userLink['DataCloningParameter']='Tools.html#cloned-environnement-managment';
$userLink['DashboardRequirement']='RequirementsTest.html#requirements-dashboard';
$userLink['DashboardTicket']='TicketDashBoard.html';
$userLink['Decision']='Steering.html#decision';
$userLink['DecisionType']='ListsOfTypes.html#decision-type';
$userLink['Deliverable']='Steering.html#deliverables';
$userLink['DeliverableStatus']='ListsOfValues.html#deliverable-status';
$userLink['DeliverableWeight']='ListsOfValues.html#deliverabl-eweight';
$userLink['Delivery']='Steering.html#deliveries';
$userLink['DeliveryMode']='ListsOfValues.html#delivery-mode';
$userLink['Document']='Document.html';
$userLink['DocumentDirectory']='Document.html#document-directory';
$userLink['DocumentExplorer']='Document.html#document-explorer';
$userLink['DocumentType']='ListsOfTypes.html#document-type';
$userLink['Diary']='Diary.html';



$userLink['Efficiency']='ListsOfValues.html#efficiency';
$userLink['EmailTemplate']='ControlAutomation.html#email-template';
$userLink['ExpenseDetailType']='ListsOfTypes.html#expense-detail-type';

$userLink['Feasibility']='ListsOfValues.html#feasibility';

$userLink['Gallery']='Incomes.html#financial-gallery';
$userLink['GlobalParameter']='GlobalParameters.html';
$userLink['GlobalPlanning']='Gantt.html#planning-global';
$userLink['GlobalView']='TransverseFeatures.html#global-view';
$userLink['GUI']='Gui.html';

$userLink['Habilitation']='AccessRights.html#access-to-forms';
$userLink['HabilitationOther']='AccessRights.html#specific-access-mode';
$userLink['HabilitationReport']='AccessRights.html#access-to-reports';
$userLink['Health']='ListsOfValues.html#health-status';
$userLink['HierarchicalBudget']='Expenses.html#hierarchical-budget';

$userLink['Import']='Tools.html#import-data';
$userLink['Imputation']='RealWorkAllocation.html';
$userLink['ImputationValidation']='RealWorkAllocation.html#timesheet-validation';
$userLink['Incoming']='Steering.html#incomings';
$userLink['IncomingStatus']='ListsOfValues.html#incoming-status';
$userLink['IncomingWeight']='ListsOfValues.html#incoming-weight';
$userLink['IndicatorDefinition']='ControlAutomation.html#indicator';
$userLink['IndicatorDefinitionPerProject']='ControlAutomation.html#indicator';
$userLink['IndividualExpense']='Expenses.html#individual-expense';
$userLink['IndividualExpenseType']='ListsOfTypes.html#individual-expense-type';
$userLink['Issue']='RiskIssueManagement.html#issue';
$userLink['IssueType']='ListsOfTypes.html#issue-type';

$userLink['JoblistDefinition']='ControlAutomation.html#jobList';

$userLink['Kanban']='Agile.html#kanban';
$userLink['KpiDefinition']='ControlAutomation.html#kpi-definitions';

$userLink['Language']='ListsOfValues.html#languages';
$userLink['leaveCalendar']='HumanResources.html#leaves-calendar';
$userLink['Leave']='HumanResources.html#leaves-periods';
$userLink['LessonLearned']='Steering.html#project-analysis';


$userLink['EmployeeLeaveEarned']='HumanResources.html#leaves-rights-earned';
$userLink['EmploymentContract']='HumanResources.html#employment-contract';
$userLink['EmployeeManager']='HumanResources.html#employee-manager';
$userLink['Employee']='HumanResources.html#employee-manager';
$userLink['EmploymentContractType']='HumanResources.html#employment-contract-type';
$userLink['EmploymentContractEndReason']='HumanResources.html#employment-contract-end-reason';

$userLink['leavesSystemHabilitation']='HumanResources.html#leaves-system-habilitation';
$userLink['LeaveType']='HumanResources.html#leaves-types';
$userLink['Likelihood']='ListsOfValues.html#likelihood';
$userLink['Location']='AssetManagement.html#location';

$userLink['Mail']='Tools.html#emails-sent';
$userLink['MailToSend']='Tools.html#emails-to-send';
$userLink['MeasureUnit']='ListsOfValues.html#measure-unit';
$userLink['Meeting']='Steering.html#meeting';
$userLink['MeetingType']='ListsOfTypes.html#meeting-type';
$userLink['Message']='Tools.html#message';
$userLink['MessageLegal']='Tools.html#legal-notice';
$userLink['MessageType']='ListsOfTypes.html#message-type';
$userLink['Milestone']='PlanningElements.html#milestone';
$userLink['MilestoneType']='ListsOfTypes.html#milestone-type';
$userLink['Model']='AssetManagement.html#models';
$userLink['Module']='AccessRights.html#module-management';

$userLink['Notification']='ControlAutomation.html#notification-system';
$userLink['NotificationDefinition']='ControlAutomation.html#notification-system';

$userLink['Opportunity']='RiskIssueManagement.html#opportunity';
$userLink['OpportunityType']='ListsOfTypes.html#opportunity-type';
$userLink['Organization']='Organization.html';
$userLink['OverallProgress']='ListsOfValues.html#overall-progress';

$userLink['Payment']='Incomes.html#client-payment';
$userLink['PaymentDelay']='ListsOfValues.html#payment-deadline';
$userLink['PaymentMode']='ListsOfValues.html#payment-method';
$userLink['PaymentType']='ListsOfTypes.html#payment-type';
$userLink['PeriodicMeeting']='Steering.html#periodic-meeting';
$userLink['Planning']='Gantt.html#planning';
$userLink['PlanningMode']='Gantt.html#planning-modes-screen';
$userLink['PlannedWorkManual']='Gantt.html#planned-interventions';
$userLink['Plugin']='Plugin.html';
$userLink['PokerComplexity']='ListOfValues.html#story-point';
$userLink['PokerSession']='Agile.html#planning-poker-session';
$userLink['PokerSessionType']='ListOfTypes.html#planning-poker-type';
$userLink['PokerSessionVoting']='Agile.html#planning-poker-estimate';
$userLink['PortfolioPlanning']='PlanningView.html#projects-portfolio';
$userLink['PredefinedNote']='ControlAutomation.html#predefined-notes';
$userLink['PredefinedSituation']='Financial.html#financial-situation';
$userLink['Priority']='ListsOfValues.html#priority';
$userLink['Product']='ConfigurationManagement.html#product';
$userLink['ProductVersion']='ConfigurationManagement.html#product-version';
$userLink['Profile']='AccessRights.html#profile';
$userLink['Project']='PlanningElements.html#project';
$userLink['ProjectDashboard']='PlanningView.html#projectsdashboard';
$userLink['ProjectExpense']='Expenses.html#project-expense';
$userLink['ProjectExpenseType']='ListsOfTypes.html#project-expense-type';
$userLink['ProjectSituation']='Financial.html#financial-situation';
$userLink['ProjectSituationExpense']='Financial.html#financial-situation';
$userLink['ProjectSituationIncome']='Financial.html#financial-situation';
$userLink['ProjectType']='ListsOfTypes.html#project-type';


$userLink['Prospect']='Customer.html#the-prospects';
$userLink['ProspectType']='ListsOfTypes.html#prospect_type';
$userLink['ProspectEventType']='ListsOfTypes.html#prospect-event_type';
$userLink['ProspectEstimateType']='ListsOfTypes.html#prospect-estimate-types';
$userLink['ProspectOrigin']='Customer.html#the-lead-events';
$userLink['DomainProspect']='Customer.html#customer-relationship-management';
$userLink['PositionProspect']='Customer.html#customer-relationship-management';
$userLink['DecisionMakerProspect']='Customer.html#customer-relationship-management';


$userLink['Provider']='Provider.html';
$userLink['ProviderBill']='Expenses.html#provider-bills';
$userLink['ProviderOrder']='Expenses.html#orders-to-provider';
$userLink['ProviderPayment']='Expenses.html#payments-to-provider';
$userLink['ProviderTerm']='Expenses.html#terms-of-payments-to-providers';
$userLink['ProviderType']='ListsOfTypes.html#provider-type';





$userLink['Quality']='ListsOfValues.html#quality-level';
$userLink['Question']='Steering.html#question';
$userLink['QuestionType']='ListsOfTypes.html#question-type';
$userLink['Quotation']='Incomes.html#client-quotation';
$userLink['QuotationType']='ListsOfTypes.html#quotation-type';




$userLink['RaciModel']='Steering.html#raci';
$userLink['Recipient']='Recipient.html';
$userLink['Report']='Report.html';
$userLink['Requirement']='RequirementsTest.html#requirement';
$userLink['RequirementType']='ListsOfTypes.html#requirement-type';
$userLink['Resolution']='ListsOfValues.html#resolution';
$userLink['Resource']='Resource.html#resource';
$userLink['ResourceMaterial']='Resource.html#material-resource';
$userLink['ResourcePlanning']='Gantt.html#resource-planning';
$userLink['ResourceTeam']='Resource.html#pool';
$userLink['Risk']='RiskIssueManagement.html#risk';
$userLink['RiskLevel']='ListsOfValues.html#risk-level';
$userLink['RiskType']='ListsOfTypes.html#risk-type';
$userLink['Role']='ListsOfValues.html#function';

$userLink['Severity']='ListsOfValues.html#severity';
$userLink['ShortCut']='Gui.html#keyboard-shortcut';
$userLink['StartGuide']='StartGuide.html';
$userLink['Status']='ListsOfValues.html#status';
$userLink['StatusMail']='ControlAutomation.html#mail-on-event';
$userLink['StatusMailPerProject']='ControlAutomation.html#mail-on-event';
$userLink['SupplierContract']='Expenses.html#supplier-contrat';

$userLink['TestCase']='RequirementsTest.html#test-case';
$userLink['TestCaseType']='ListsOfTypes.html#test-case-type';
$userLink['TestSession']='RequirementsTest.html#test-session';
$userLink['TestSessionType']='ListsOfTypes.html#test-session-type';
$userLink['Team']='Resource.html#team';
$userLink['Tender']='Expenses.html#tenders';
$userLink['Term']='Incomes.html#client-billing-term';
$userLink['Ticket']='Ticket.html#ticket';
$userLink['TicketDelay']='ControlAutomation.html#delay-for-ticket';
$userLink['TicketDelayPerProject']='ControlAutomation.html#delay-for-ticket';
$userLink['TicketSimple']='Ticket.html#simple-ticket';
$userLink['TicketType']='ListsOfTypes.html#ticket-type';
$userLink['InputMailboxTicket']='Ticket.html#ticket-fromemail';
$userLink['TransverseFeatures']='TransverseFeatures.html';
$userLink['Trend']='ListsOfValues.html#trend';
$userLink['Today']='Today.html';

$userLink['Urgency']='ListsOfValues.html#urgency';
$userLink['User']='User.html#user';
$userLink['UserParameter']='UserParameter.html';

$userLink['VersionsPlanning']='ConfigurationManagement.html#versions-planning';
$userLink['VotingAttributionRule']='Collaboration.html#voting-attribution-rule';
$userLink['VotingAttributionFollowUp']='Collaboration.html#voting-attribution-follow-up';
$userLink['VotingFollowUp']='Collaboration.html#voting-follow-up';
$userLink['VotingUseRule']='Collaboration.html#voting-use-rule';
$userLink['VotingUseRulePerProject']='Collaboration.html#voting-use-rule';

$userLink['WorkCommand']='Incomes.html#work-commands';
$userLink['Workflow']='ControlAutomation.html#workflow';
$userLink['WorkPlan']='PlanningView.html#planning-dynamic-work-plan';

$section=null;
if (isset($_REQUEST['section'])) {
  $section=$_REQUEST['section']; // Note: can only be a valid index in $userLink. Value is not echo'ed in HTML.
}

$tab=null;
if (isset($_REQUEST['tab'])) {
  $tab=$_REQUEST['tab']; // Note: can only be a valid index in $userLink. Value is not echo'ed in HTML.
}

if (pq_substr($section,0,7)=='Plugin_') {
  $plugin=pq_substr($section,7);
  $pluginRoot="../plugin/$plugin/docs";
  if (file_exists("$pluginRoot/$plugin.html")) {
    $url="$pluginRoot/$plugin.html";
    echo $url;
    exit;
  } else if (file_exists("$pluginRoot/$plugin.pdf")) {
    $url="$pluginRoot/$plugin.pdf";
    echo $url;
    exit;
  } else {
    $section="Plugin";
  }
}

$userRoot='../docs/user/html_en/';
$userLang = getSessionValue('currentLocale');
if (!$userLang and isset($currentLocale)) $userLang=$currentLocale;
if (pq_substr($userLang,0,2)=='fr' and file_exists('../docs/user/html_fr/')) $userRoot='../docs/user/html_fr/';
$url=$userRoot.$userLink['Welcome'];
if ($section and isset($userLink[$section])) {
  $url=$userRoot.$userLink[$section];
} 
if ($tab and $tab!='null' and pq_strpos($url,'#')===false) {
  if ($section=="GlobalParameter") $url.='#tab-'.pq_strtolower($tab);
  else $url.='#'.pq_strtolower($tab);
}
echo $url;
